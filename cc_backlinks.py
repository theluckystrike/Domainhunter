#!/usr/bin/env python3
"""
CommonCrawl Web Graph Backlinks Analyzer

Query domain-level backlinks from CommonCrawl Web Graph without downloading full dataset.
Uses DuckDB for efficient local querying of compressed graph data.

Usage:
    from cc_backlinks import CCBacklinksAnalyzer

    analyzer = CCBacklinksAnalyzer()
    analyzer.setup()  # One-time: download and convert

    # Query single domain
    results = analyzer.query_domain('example.com')

    # Batch query
    domains = ['example.com', 'github.com', 'stackoverflow.com']
    batch_results = analyzer.query_batch(domains)

Cost: $0 (using free CloudFront HTTPS or same-region S3)
Performance: <1 sec for 200 domains (cached)
Data freshness: 0-2 months old
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BacklinkResult:
    """Single backlink result"""
    referring_domain: str
    backlink_count: int
    unique_subdomains: int
    estimated_quality: str  # 'High', 'Medium', 'Low'


@dataclass
class DomainBacklinks:
    """Backlinks for a single domain"""
    domain: str
    total_backlinks: int
    total_referring_domains: int
    top_referrers: List[BacklinkResult]
    error: Optional[str] = None


class CCBacklinksAnalyzer:
    """
    CommonCrawl Web Graph backlinks analyzer using DuckDB.

    Manages graph download, conversion to Parquet, and efficient SQL queries.
    """

    def __init__(
        self,
        data_dir: str = "./.cc-data",
        graph_release: str = "cc-main-2026-feb-mar-apr",
        graph_base_url: str = "https://data.commoncrawl.org/projects/hyperlinkgraph",
        vertex_files: int = 30,
        edge_files: int = 30,
        max_parallel_downloads: int = 5,
    ):
        """
        Initialize analyzer.

        Args:
            data_dir: Directory to store graph data
            graph_release: CommonCrawl graph release name
            graph_base_url: Base URL for CommonCrawl graphs
            vertex_files: Number of vertex files to download
            edge_files: Number of edge files to download
            max_parallel_downloads: Max concurrent downloads
        """
        self.data_dir = Path(data_dir)
        self.graph_release = graph_release
        self.graph_base_url = graph_base_url
        self.vertex_files = vertex_files
        self.edge_files = edge_files
        self.max_parallel_downloads = max_parallel_downloads

        # Check dependencies
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check required tools are installed."""
        try:
            subprocess.run(["duckdb", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "duckdb not found. Install from: https://duckdb.org/docs/installation"
            )

        try:
            subprocess.run(["curl", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("curl not found")

    def setup(self) -> bool:
        """
        One-time setup: download graph files and convert to Parquet.

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Setting up CommonCrawl Web Graph ({self.graph_release})")

        # Check if already setup
        if self._is_setup_complete():
            logger.info("Graph already downloaded and converted. Use update() to refresh.")
            return True

        self.data_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Download files
            logger.info(f"Downloading {self.vertex_files} vertex files...")
            self._download_graph_files("domain.vertices", self.vertex_files)

            logger.info(f"Downloading {self.edge_files} edge files...")
            self._download_graph_files("domain.edges", self.edge_files)

            # Convert to Parquet
            logger.info("Converting to Parquet format...")
            self._convert_to_parquet()

            logger.info("Setup complete!")
            return True

        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

    def _is_setup_complete(self) -> bool:
        """Check if Parquet files exist."""
        vertices_file = self.data_dir / "vertices.parquet"
        edges_file = self.data_dir / "edges.parquet"
        return vertices_file.exists() and edges_file.exists()

    def _download_graph_files(self, file_pattern: str, count: int) -> None:
        """Download graph files with parallel queue."""
        def download_file(file_num: int) -> Tuple[int, bool]:
            file_name = f"{file_pattern}-{file_num:05d}.gz"
            file_path = self.data_dir / file_name
            file_url = f"{self.graph_base_url}/{self.graph_release}/domain/{file_name}"

            if file_path.exists():
                logger.debug(f"File already exists: {file_name}")
                return file_num, True

            try:
                logger.debug(f"Downloading {file_name}...")
                urllib.request.urlretrieve(file_url, file_path)
                logger.debug(f"Downloaded {file_name}")
                return file_num, True
            except Exception as e:
                logger.error(f"Failed to download {file_name}: {e}")
                return file_num, False

        with ThreadPoolExecutor(max_workers=self.max_parallel_downloads) as executor:
            futures = [
                executor.submit(download_file, i)
                for i in range(count)
            ]
            completed = 0
            for future in as_completed(futures):
                completed += 1
                file_num, success = future.result()
                if completed % 5 == 0:
                    logger.info(f"Downloaded {completed}/{count} files")

    def _convert_to_parquet(self) -> None:
        """Convert gzipped CSV to Parquet format."""
        duckdb_script = f"""
        -- Load vertices
        CREATE TEMP TABLE vertices AS
        SELECT * FROM read_csv_auto('{self.data_dir}/domain.vertices-*.gz',
          columns={{id: 'BIGINT', domain: 'VARCHAR', hosts: 'BIGINT'}},
          sep='\t',
          header=false);

        -- Load edges
        CREATE TEMP TABLE edges AS
        SELECT * FROM read_csv_auto('{self.data_dir}/domain.edges-*.gz',
          columns={{source: 'BIGINT', target: 'BIGINT'}},
          sep='\t',
          header=false);

        -- Export to Parquet
        COPY vertices TO '{self.data_dir}/vertices.parquet' (FORMAT PARQUET);
        COPY edges TO '{self.data_dir}/edges.parquet' (FORMAT PARQUET);
        """

        try:
            result = subprocess.run(
                ["duckdb"],
                input=duckdb_script,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("Parquet conversion successful")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Parquet conversion failed: {e.stderr}")

    def query_domain(
        self,
        domain: str,
        limit: int = 50,
        min_hosts: int = 0,
    ) -> DomainBacklinks:
        """
        Query backlinks for a single domain.

        Args:
            domain: Domain to query (e.g., 'example.com')
            limit: Max results to return
            min_hosts: Minimum unique subdomains threshold

        Returns:
            DomainBacklinks object with results
        """
        if not self._is_setup_complete():
            return DomainBacklinks(
                domain=domain,
                total_backlinks=0,
                total_referring_domains=0,
                top_referrers=[],
                error="Graph not setup. Call setup() first.",
            )

        try:
            reversed_domain = self._reverse_domain(domain)
            logger.debug(f"Querying backlinks for: {domain}")

            duckdb_script = f"""
            SELECT
              domain AS referring_domain,
              COUNT(*) AS backlink_count,
              SUM(hosts) AS unique_subdomains,
              CASE
                WHEN SUM(hosts) >= 100 THEN 'High'
                WHEN SUM(hosts) >= 10 THEN 'Medium'
                ELSE 'Low'
              END AS estimated_quality
            FROM (
              SELECT v.domain, v.hosts
              FROM read_parquet('{self.data_dir}/edges.parquet') e
              JOIN read_parquet('{self.data_dir}/vertices.parquet') v ON e.source = v.id
              WHERE e.target = (
                SELECT id FROM read_parquet('{self.data_dir}/vertices.parquet')
                WHERE domain = '{reversed_domain}' LIMIT 1
              )
              AND e.source != e.target
              AND v.hosts >= {min_hosts}
            )
            GROUP BY domain
            ORDER BY backlink_count DESC
            LIMIT {limit};
            """

            result = subprocess.run(
                ["duckdb"],
                input=duckdb_script,
                capture_output=True,
                text=True,
                check=True,
            )

            # Parse results
            referrers = []
            total_backlinks = 0
            total_referring = 0

            for line in result.stdout.strip().split('\n'):
                if not line or '|' not in line:
                    continue

                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    try:
                        referring_domain = parts[0]
                        backlink_count = int(parts[1])
                        unique_subdomains = int(parts[2])
                        quality = parts[3]

                        referrers.append(BacklinkResult(
                            referring_domain=referring_domain,
                            backlink_count=backlink_count,
                            unique_subdomains=unique_subdomains,
                            estimated_quality=quality,
                        ))
                        total_backlinks += backlink_count
                        total_referring += 1
                    except (ValueError, IndexError):
                        continue

            return DomainBacklinks(
                domain=domain,
                total_backlinks=total_backlinks,
                total_referring_domains=total_referring,
                top_referrers=referrers,
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Query failed for {domain}: {e.stderr}")
            return DomainBacklinks(
                domain=domain,
                total_backlinks=0,
                total_referring_domains=0,
                top_referrers=[],
                error=f"Query failed: {e.stderr}",
            )

    def query_batch(
        self,
        domains: List[str],
        limit: int = 50,
        parallel: int = 4,
    ) -> Dict[str, DomainBacklinks]:
        """
        Query backlinks for multiple domains in parallel.

        Args:
            domains: List of domains to query
            limit: Max results per domain
            parallel: Number of parallel queries

        Returns:
            Dict mapping domain -> DomainBacklinks
        """
        logger.info(f"Processing {len(domains)} domains (parallel={parallel})")

        results = {}
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(self.query_domain, domain, limit): domain
                for domain in domains
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                domain = futures[future]
                try:
                    result = future.result()
                    results[domain] = result
                    logger.info(
                        f"[{completed}/{len(domains)}] {domain}: "
                        f"{result.total_backlinks} backlinks from {result.total_referring_domains} domains"
                    )
                except Exception as e:
                    logger.error(f"[{completed}/{len(domains)}] {domain}: {e}")
                    results[domain] = DomainBacklinks(
                        domain=domain,
                        total_backlinks=0,
                        total_referring_domains=0,
                        top_referrers=[],
                        error=str(e),
                    )

        return results

    def get_graph_stats(self) -> Dict:
        """Get basic graph statistics."""
        if not self._is_setup_complete():
            return {"error": "Graph not setup. Call setup() first."}

        duckdb_script = f"""
        SELECT COUNT(*) as vertices FROM read_parquet('{self.data_dir}/vertices.parquet');
        SELECT COUNT(*) as edges FROM read_parquet('{self.data_dir}/edges.parquet');
        """

        try:
            result = subprocess.run(
                ["duckdb"],
                input=duckdb_script,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Graph statistics:\n{result.stdout}")
            return {"status": "success"}
        except subprocess.CalledProcessError as e:
            return {"error": f"Failed to get stats: {e.stderr}"}

    def get_cc_rank(self, domain: str) -> int:
        """Get in-degree count for a domain from CommonCrawl graph.

        Lightweight authority signal: how many other domains link to this one.
        Returns 0 if graph not setup or domain not found.

        Args:
            domain: Domain to check (e.g. 'example.com').

        Returns:
            In-degree count (number of referring domains in CC graph).
        """
        if not self._is_setup_complete():
            return 0

        reversed_domain = self._reverse_domain(domain)

        duckdb_script = f"""
        SELECT COUNT(*) AS in_degree
        FROM read_parquet('{self.data_dir}/edges.parquet') e
        WHERE e.target = (
            SELECT id FROM read_parquet('{self.data_dir}/vertices.parquet')
            WHERE domain = '{reversed_domain}' LIMIT 1
        );
        """

        try:
            result = subprocess.run(
                ["duckdb"],
                input=duckdb_script,
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line.isdigit():
                    return int(line)
            return 0
        except subprocess.CalledProcessError:
            return 0

    @staticmethod
    def _reverse_domain(domain: str) -> str:
        """Convert domain to reverse notation: example.com -> com.example"""
        return '.'.join(reversed(domain.split('.')))

    def export_results(self, results: Dict[str, DomainBacklinks], output_file: str) -> None:
        """Export query results to JSON."""
        export_data = {
            "graph_release": self.graph_release,
            "domains": {}
        }

        for domain, backlinks in results.items():
            export_data["domains"][domain] = {
                "total_backlinks": backlinks.total_backlinks,
                "total_referring_domains": backlinks.total_referring_domains,
                "error": backlinks.error,
                "top_referrers": [
                    {
                        "domain": r.referring_domain,
                        "backlinks": r.backlink_count,
                        "subdomains": r.unique_subdomains,
                        "quality": r.estimated_quality,
                    }
                    for r in backlinks.top_referrers
                ]
            }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Results exported to {output_file}")


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CommonCrawl Web Graph Backlinks Analyzer"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Setup command
    subparsers.add_parser("setup", help="One-time setup: download and convert graph")

    # Query single domain
    query_parser = subparsers.add_parser("query", help="Query single domain")
    query_parser.add_argument("domain", help="Domain to query (e.g., example.com)")
    query_parser.add_argument("--limit", type=int, default=50, help="Max results")

    # Batch query
    batch_parser = subparsers.add_parser("query-batch", help="Query multiple domains")
    batch_parser.add_argument("file", help="File with domains (one per line)")
    batch_parser.add_argument("--limit", type=int, default=50, help="Max results per domain")
    batch_parser.add_argument("--parallel", type=int, default=4, help="Parallel queries")
    batch_parser.add_argument("--output", help="Output JSON file")

    # Stats command
    subparsers.add_parser("stats", help="Show graph statistics")

    args = parser.parse_args()

    analyzer = CCBacklinksAnalyzer()

    if args.command == "setup":
        analyzer.setup()

    elif args.command == "query":
        result = analyzer.query_domain(args.domain, limit=args.limit)
        print(json.dumps({
            "domain": result.domain,
            "total_backlinks": result.total_backlinks,
            "total_referring_domains": result.total_referring_domains,
            "error": result.error,
            "top_referrers": [
                {
                    "domain": r.referring_domain,
                    "backlinks": r.backlink_count,
                    "subdomains": r.unique_subdomains,
                    "quality": r.estimated_quality,
                }
                for r in result.top_referrers
            ]
        }, indent=2))

    elif args.command == "query-batch":
        with open(args.file) as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        results = analyzer.query_batch(domains, limit=args.limit, parallel=args.parallel)

        if args.output:
            analyzer.export_results(results, args.output)
        else:
            for domain, backlinks in results.items():
                print(f"\n{domain}:")
                print(f"  Total backlinks: {backlinks.total_backlinks}")
                print(f"  Referring domains: {backlinks.total_referring_domains}")
                if backlinks.error:
                    print(f"  Error: {backlinks.error}")
                for r in backlinks.top_referrers[:5]:
                    print(f"    - {r.referring_domain}: {r.backlink_count} links")

    elif args.command == "stats":
        analyzer.get_graph_stats()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

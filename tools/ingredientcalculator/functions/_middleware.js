// Pages Function middleware: 301 redirect www -> apex, then pass through.
// www.ingredientcalculator.com is a custom domain on this Pages project and
// would otherwise serve identical content. This consolidates it to the apex.
export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname === "www.ingredientcalculator.com") {
    url.hostname = "ingredientcalculator.com";
    return new Response(null, { status: 301, headers: { "Location": url.toString() } });
  }
  return context.next();
}

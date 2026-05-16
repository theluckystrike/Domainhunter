-- dropcatch_backorder.scpt
-- Opens a DropCatch backorder page for a given domain in Google Chrome.
-- Usage: osascript dropcatch_backorder.scpt "guerrameats.com"
-- Falls back to Safari if Chrome is not installed.
--
-- NOTE: This navigates TO the page. The user clicks "Backorder" manually.
-- DropCatch DOES have a REST API (v2) via NameBright OAuth2.
-- See clients/dropcatch_client.py for programmatic access.
-- This AppleScript is the manual/browser alternative.

on run argv
    -- Validate argument count
    if (count of argv) < 1 then
        display dialog "Usage: osascript dropcatch_backorder.scpt <domain>" buttons {"OK"} default button "OK" with icon stop
        error "Missing domain argument" number 1
    end if

    set domainName to item 1 of argv
    set targetURL to "https://www.dropcatch.com/snap/listing/" & domainName

    -- Try Google Chrome first, fall back to Safari
    set browserApp to "Google Chrome"
    try
        tell application "Finder"
            set chromeExists to exists application file id "com.google.Chrome"
        end tell
    on error
        set chromeExists to false
    end try

    if chromeExists then
        tell application "Google Chrome"
            activate
            if (count of windows) = 0 then
                make new window
                set URL of active tab of front window to targetURL
            else
                tell front window
                    make new tab with properties {URL:targetURL}
                end tell
            end if
        end tell
        log "Opened in Chrome: " & targetURL
    else
        -- Safari fallback
        tell application "Safari"
            activate
            if (count of windows) = 0 then
                make new document with properties {URL:targetURL}
            else
                tell front window
                    set current tab to (make new tab with properties {URL:targetURL})
                end tell
            end if
        end tell
        log "Opened in Safari: " & targetURL
    end if

    return targetURL
end run

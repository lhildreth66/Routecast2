"""Installable owner console assets. No business data or offline caching."""
import json
import struct
import zlib

def icon(size):
    # Blue geometric H mark with a teal accent, rendered as PNG without dependencies.
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            u, v = x/size, y/size
            color = (16, 43, 78)
            if .23 <= u <= .35 and .22 <= v <= .78 or .65 <= u <= .77 and .22 <= v <= .78:
                color = (245, 249, 255)
            if .35 < u < .65 and .43 <= v <= .57:
                color = (66, 207, 229)
            row.extend(color)
        rows.append(bytes(row))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data)&0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",size,size,8,2,0,0,0)) + chunk(b"IDAT",zlib.compress(b"".join(rows))) + chunk(b"IEND",b"")

MANIFEST = json.dumps({"name":"Hildreth Technologies Dashboard","short_name":"Hildreth Admin","id":"/","start_url":"/","scope":"/","display":"standalone","background_color":"#f3f6fb","theme_color":"#102b4e","icons":[{"src":"/icon-192.png","sizes":"192x192","type":"image/png"},{"src":"/icon-512.png","sizes":"512x512","type":"image/png"}]}).encode()
ASSETS = {
    "/manifest.webmanifest": ("application/manifest+json", MANIFEST),
    "/icon-192.png": ("image/png", icon(192)),
    "/icon-512.png": ("image/png", icon(512)),
    "/sw.js": ("application/javascript", b"self.addEventListener('fetch', () => {});"),
    "/install.js": ("application/javascript", b"if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});")
}
HEAD = '<link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/icon-192.png"><link rel="apple-touch-icon" href="/icon-192.png"><meta name="theme-color" content="#102b4e"><script src="/install.js" defer></script>'

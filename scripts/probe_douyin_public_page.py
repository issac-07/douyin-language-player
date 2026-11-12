"""Read-only public HTML probe. No cookies, signatures, JavaScript or challenge execution."""
import json
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.safe_http import RequestContext, SafeHTTPClient

MOBILE_UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'


def main():
    video_id = sys.argv[1]
    if not video_id.isascii() or not video_id.isdigit(): raise ValueError('Numeric public video ID required')
    client = SafeHTTPClient(RequestContext(threading.Event(), 30))
    with client.open(f'https://www.iesdouyin.com/share/video/{video_id}/', role='page', headers={'User-Agent': MOBILE_UA}) as response:
        body = response.read().decode('utf-8')
    marker = body.index('window._ROUTER_DATA')
    payload, _ = json.JSONDecoder().raw_decode(body[body.index('=', marker) + 1:].lstrip())
    print('loader keys:', list(payload.get('loaderData', {})))
    for route in payload.get('loaderData', {}).values():
        print('route keys:', list(route) if isinstance(route, dict) else type(route).__name__)
        result = route.get('videoInfoRes', {}) if isinstance(route, dict) else {}
        print('response keys:', list(result), 'status:', result.get('status_code'))
        for item in result.get('item_list', []):
            video = item.get('video', {})
            print(json.dumps({'id': item.get('aweme_id'), 'item_keys': list(item), 'video_keys': list(video),
                  'duration': video.get('duration'), 'type': item.get('aweme_type'),
                  'status': item.get('status'), 'play_hosts': [urlsplit(url).hostname for url in video.get('play_addr', {}).get('url_list', [])]}, ensure_ascii=False))


if __name__ == '__main__': main()

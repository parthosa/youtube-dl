from __future__ import unicode_literals

import functools
import re

from .common import InfoExtractor
from ..compat import (
    compat_urllib_parse_unquote,
    compat_urlparse,
)
from ..utils import (
    clean_html,
    ExtractorError,
    HEADRequest,
    OnDemandPagedList,
    NO_DEFAULT,
    parse_count,
    str_to_int,
)


class MixcloudIE(InfoExtractor):
    _VALID_URL = r'^(?:https?://)?(?:www\.)?mixcloud\.com/([^/]+)/(?!stream|uploads|favorites|listens|playlists)([^/]+)'
    IE_NAME = 'mixcloud'

    _TESTS = [{
        'url': 'http://www.mixcloud.com/dholbach/cryptkeeper/',
        'info_dict': {
            'id': 'dholbach-cryptkeeper',
            'ext': 'm4a',
            'title': 'Cryptkeeper',
            'description': 'After quite a long silence from myself, finally another Drum\'n\'Bass mix with my favourite current dance floor bangers.',
            'uploader': 'Daniel Holbach',
            'uploader_id': 'dholbach',
            'thumbnail': 're:https?://.*\.jpg',
            'view_count': int,
            'like_count': int,
        },
    }, {
        'url': 'http://www.mixcloud.com/gillespeterson/caribou-7-inch-vinyl-mix-chat/',
        'info_dict': {
            'id': 'gillespeterson-caribou-7-inch-vinyl-mix-chat',
            'ext': 'mp3',
            'title': 'Caribou 7 inch Vinyl Mix & Chat',
            'description': 'md5:2b8aec6adce69f9d41724647c65875e8',
            'uploader': 'Gilles Peterson Worldwide',
            'uploader_id': 'gillespeterson',
            'thumbnail': 're:https?://.*/images/',
            'view_count': int,
            'like_count': int,
        },
    }]

    def _check_url(self, url, track_id, ext):
        try:
            # We only want to know if the request succeed
            # don't download the whole file
            self._request_webpage(
                HEADRequest(url), track_id,
                'Trying %s URL' % ext)
            return True
        except ExtractorError:
            return False

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        uploader = mobj.group(1)
        cloudcast_name = mobj.group(2)
        track_id = compat_urllib_parse_unquote('-'.join((uploader, cloudcast_name)))

        webpage = self._download_webpage(url, track_id)

        message = self._html_search_regex(
            r'(?s)<div[^>]+class="global-message cloudcast-disabled-notice-light"[^>]*>(.+?)<(?:a|/div)',
            webpage, 'error message', default=None)

        preview_url = self._search_regex(
            r'\s(?:data-preview-url|m-preview)="([^"]+)"',
            webpage, 'preview url', default=None if message else NO_DEFAULT)

        if message:
            raise ExtractorError('%s said: %s' % (self.IE_NAME, message), expected=True)

        song_url = re.sub(r'audiocdn(\d+)', r'stream\1', preview_url)
        song_url = song_url.replace('/previews/', '/c/originals/')
        if not self._check_url(song_url, track_id, 'mp3'):
            song_url = song_url.replace('.mp3', '.m4a').replace('originals/', 'm4a/64/')
            if not self._check_url(song_url, track_id, 'm4a'):
                raise ExtractorError('Unable to extract track url')

        PREFIX = (
            r'm-play-on-spacebar[^>]+'
            r'(?:\s+[a-zA-Z0-9-]+(?:="[^"]+")?)*?\s+')
        title = self._html_search_regex(
            PREFIX + r'm-title="([^"]+)"', webpage, 'title')
        thumbnail = self._proto_relative_url(self._html_search_regex(
            PREFIX + r'm-thumbnail-url="([^"]+)"', webpage, 'thumbnail',
            fatal=False))
        uploader = self._html_search_regex(
            PREFIX + r'm-owner-name="([^"]+)"',
            webpage, 'uploader', fatal=False)
        uploader_id = self._search_regex(
            r'\s+"profile": "([^"]+)",', webpage, 'uploader id', fatal=False)
        description = self._og_search_description(webpage)
        like_count = parse_count(self._search_regex(
            r'\bbutton-favorite[^>]+>.*?<span[^>]+class=["\']toggle-number[^>]+>\s*([^<]+)',
            webpage, 'like count', fatal=False))
        view_count = str_to_int(self._search_regex(
            [r'<meta itemprop="interactionCount" content="UserPlays:([0-9]+)"',
             r'/listeners/?">([0-9,.]+)</a>'],
            webpage, 'play count', fatal=False))

        return {
            'id': track_id,
            'title': title,
            'url': song_url,
            'description': description,
            'thumbnail': thumbnail,
            'uploader': uploader,
            'uploader_id': uploader_id,
            'view_count': view_count,
            'like_count': like_count,
        }


class MixcloudPlaylistBaseIE(InfoExtractor):
    _PAGE_SIZE = 24

    def _fetch_tracks_page(self, path, video_id, page_name, current_page):
        resp = self._download_webpage(
            'https://www.mixcloud.com/%s/' % path, video_id,
            note='Download %s (page %d)' % (page_name, current_page + 1),
            errnote='Unable to download %s' % page_name,
            query={'page': (current_page + 1), 'list': 'main', '_ajax': '1'},
            headers={'X-Requested-With': 'XMLHttpRequest'})

        for url in re.findall(r'm-play-button m-url="(?P<url>[^"]+)"', resp):
            yield self.url_result(
                compat_urlparse.urljoin('https://www.mixcloud.com', clean_html(url)),
                MixcloudIE.ie_key())

    def _get_user_description(self, page_content):
        return self._html_search_regex(
            r'<div[^>]+class="description-text"[^>]*>(.+?)</div>',
            page_content, 'user description', fatal=False)


class MixcloudUserIE(MixcloudPlaylistBaseIE):
    _VALID_URL = r'^(?:https?://)?(?:www\.)?mixcloud\.com/(?P<user>[^/]+)/(?P<type>uploads|favorites|listens)?/?$'
    IE_NAME = 'mixcloud:user'

    _TESTS = [{
        'url': 'http://www.mixcloud.com/dholbach/',
        'info_dict': {
            'id': 'dholbach_uploads',
            'title': 'Daniel Holbach (uploads)',
            'description': 'md5:327af72d1efeb404a8216c27240d1370',
        },
        'playlist_mincount': 11,
    }, {
        'url': 'http://www.mixcloud.com/dholbach/uploads/',
        'info_dict': {
            'id': 'dholbach_uploads',
            'title': 'Daniel Holbach (uploads)',
            'description': 'md5:327af72d1efeb404a8216c27240d1370',
        },
        'playlist_mincount': 11,
    }, {
        'url': 'http://www.mixcloud.com/dholbach/favorites/',
        'info_dict': {
            'id': 'dholbach_favorites',
            'title': 'Daniel Holbach (favorites)',
            'description': 'md5:327af72d1efeb404a8216c27240d1370',
        },
        'params': {
            'playlist_items': '1-100',
        },
        'playlist_mincount': 100,
    }, {
        'url': 'http://www.mixcloud.com/dholbach/listens/',
        'info_dict': {
            'id': 'dholbach_listens',
            'title': 'Daniel Holbach (listens)',
            'description': 'md5:327af72d1efeb404a8216c27240d1370',
        },
        'params': {
            'playlist_items': '1-100',
        },
        'playlist_mincount': 100,
    }]

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        user_id = mobj.group('user')
        list_type = mobj.group('type')

        # if only a profile URL was supplied, default to download all uploads
        if list_type is None:
            list_type = 'uploads'

        video_id = '%s_%s' % (user_id, list_type)

        profile = self._download_webpage(
            'https://www.mixcloud.com/%s/' % user_id, video_id,
            note='Downloading user profile',
            errnote='Unable to download user profile')

        username = self._og_search_title(profile)
        description = self._get_user_description(profile)

        entries = OnDemandPagedList(
            functools.partial(
                self._fetch_tracks_page,
                '%s/%s' % (user_id, list_type), video_id, 'list of %s' % list_type),
            self._PAGE_SIZE, use_cache=True)

        return self.playlist_result(
            entries, video_id, '%s (%s)' % (username, list_type), description)


class MixcloudPlaylistIE(MixcloudPlaylistBaseIE):
    _VALID_URL = r'^(?:https?://)?(?:www\.)?mixcloud\.com/(?P<user>[^/]+)/playlists/(?P<playlist>[^/]+)/?$'
    IE_NAME = 'mixcloud:playlist'

    _TESTS = [{
        'url': 'https://www.mixcloud.com/RedBullThre3style/playlists/tokyo-finalists-2015/',
        'info_dict': {
            'id': 'RedBullThre3style_tokyo-finalists-2015',
            'title': 'National Champions 2015',
            'description': 'md5:6ff5fb01ac76a31abc9b3939c16243a3',
        },
        'playlist_mincount': 16,
    }, {
        'url': 'https://www.mixcloud.com/maxvibes/playlists/jazzcat-on-ness-radio/',
        'info_dict': {
            'id': 'maxvibes_jazzcat-on-ness-radio',
            'title': 'Jazzcat on Ness Radio',
            'description': 'md5:7bbbf0d6359a0b8cda85224be0f8f263',
        },
        'playlist_mincount': 23
    }]

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        user_id = mobj.group('user')
        playlist_id = mobj.group('playlist')
        video_id = '%s_%s' % (user_id, playlist_id)

        profile = self._download_webpage(
            url, user_id,
            note='Downloading playlist page',
            errnote='Unable to download playlist page')

        description = self._get_user_description(profile)
        playlist_title = self._html_search_regex(
            r'<span[^>]+class="[^"]*list-playlist-title[^"]*"[^>]*>(.*?)</span>',
            profile, 'playlist title')

        entries = OnDemandPagedList(
            functools.partial(
                self._fetch_tracks_page,
                '%s/playlists/%s' % (user_id, playlist_id), video_id, 'tracklist'),
            self._PAGE_SIZE)

        return self.playlist_result(entries, video_id, playlist_title, description)

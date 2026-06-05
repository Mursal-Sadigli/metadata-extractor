/**
 * Tərs şəkil portal linkləri — Python portal_search_urls.py ilə uyğun.
 */

export function isFetchableImageUrl(url) {
  if (!url || typeof url !== 'string' || !/^https?:\/\//i.test(url)) return false;
  return !/localhost|127\.0\.0\.1/i.test(url);
}

/** URL yükləmədən sonra: resolved_url və ya source_url */
export function resolveSearchImageUrl(file) {
  if (!file) return null;
  const candidates = [
    file.resolved_url,
    file.source_url,
    file.search_image_url,
    file.public_image_url,
  ];
  for (const u of candidates) {
    if (isFetchableImageUrl(u)) return u;
  }
  return null;
}

export function buildPortalSearchLinks(searchUrl) {
  if (!isFetchableImageUrl(searchUrl)) {
    return [];
  }
  const enc = encodeURIComponent(searchUrl);
  return [
    {
      id: 'google_lens',
      name: 'Google Lens',
      search_url: `https://lens.google.com/uploadbyurl?url=${enc}`,
      method: 'url',
      note_az: 'Şəkil URL ilə avtomatik Lens axtarışı',
    },
    {
      id: 'google_images',
      name: 'Google Images',
      search_url: `https://www.google.com/searchbyimage?image_url=${enc}&safe=off`,
      method: 'url',
      note_az: 'Google — şəkil URL ilə tərs axtarış',
    },
    {
      id: 'yandex_images',
      name: 'Yandex Images',
      search_url: `https://yandex.com/images/search?rpt=imageview&url=${enc}`,
      method: 'url',
      note_az: 'Yandex — şəkil URL ilə avtomatik axtarış',
    },
    {
      id: 'tineye_web',
      name: 'TinEye (veb)',
      search_url: `https://tineye.com/search?url=${enc}`,
      method: 'url',
      note_az: 'TinEye — şəkil URL ilə avtomatik axtarış',
    },
    {
      id: 'tineye',
      name: 'TinEye',
      search_url: `https://tineye.com/search?url=${enc}`,
      method: 'url',
      note_az: 'TinEye — eyni URL axtarışı',
    },
    {
      id: 'bing_images',
      name: 'Bing Images',
      search_url: `https://www.bing.com/images/search?view=detailv2&iss=sbiupload&sbisrc=ImgPaste&q=imgurl:${enc}`,
      method: 'url',
      note_az: 'Bing — şəkil URL ilə tərs axtarış',
    },
    {
      id: 'pimeyes',
      name: 'PimEyes',
      search_url: 'https://pimeyes.com/en',
      method: 'manual_upload',
      note_az: 'PimEyes URL ilə avtomatik açmır — faylı əl ilə yükləyin',
      privacy_warning: true,
    },
  ];
}

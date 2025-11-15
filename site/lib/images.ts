import { cache } from 'react';

const decodeHtmlEntities = (value: string) =>
  value
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");

const extractMetaContent = (html: string, key: string) => {
  const metaRegex = new RegExp(
    `<meta[^>]+(?:property|name)=["']${key}["'][^>]*>`,
    'i'
  );
  const match = html.match(metaRegex);
  if (!match) {
    return null;
  }

  const contentMatch = match[0].match(/content=["']([^"']+)["']/i);
  return contentMatch ? decodeHtmlEntities(contentMatch[1]) : null;
};

const extractFallbackImage = (html: string) => {
  const match = html.match(/<img[^>]+src=["']([^"']+)["'][^>]*>/i);
  return match ? decodeHtmlEntities(match[1]) : null;
};

const resolveImageUrl = (imageUrl: string, baseUrl: string) => {
  try {
    return new URL(imageUrl, baseUrl).toString();
  } catch {
    return imageUrl;
  }
};

export const fetchRecipeImage = cache(async (sourceUrl: string): Promise<string | null> => {
  if (!sourceUrl) {
    return null;
  }

  try {
    const response = await fetch(sourceUrl, {
      headers: {
        'User-Agent': 'Planthood timeline viewer',
      },
      next: {
        revalidate: 60 * 60 * 24, // Cache for 24 hours
      },
    });

    if (!response.ok) {
      return null;
    }

    const html = await response.text();
    const metaImage =
      extractMetaContent(html, 'og:image') ||
      extractMetaContent(html, 'twitter:image') ||
      extractMetaContent(html, 'image');
    const fallbackImage = extractFallbackImage(html);
    const rawImage = metaImage || fallbackImage;

    if (!rawImage) {
      return null;
    }

    return resolveImageUrl(rawImage, sourceUrl);
  } catch (error) {
    console.warn('Failed to fetch recipe image for', sourceUrl, error);
    return null;
  }
});

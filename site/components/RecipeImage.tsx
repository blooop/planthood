'use client';

import { useState } from 'react';

interface RecipeImageProps {
  src: string | null;
  alt: string;
  placeholderClassName: string;
  placeholderText: string;
}

/**
 * Image with a graceful fallback. The URL is resolved at build time; this component
 * additionally handles the case where the remote image 404s at view time (onError),
 * falling back to the placeholder instead of showing a broken-image icon.
 */
export default function RecipeImage({
  src,
  alt,
  placeholderClassName,
  placeholderText,
}: RecipeImageProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div className={placeholderClassName}>
        <span>{placeholderText}</span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />
  );
}

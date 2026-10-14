import { useId, type ReactNode } from "react";

export type NeetCodeCourseArtworkVariant = "learning" | "project" | "career";

export function NeetCodeCourseCard({
  artwork,
  children,
  className = "",
  labelledBy,
}: {
  artwork: ReactNode;
  children?: ReactNode;
  className?: string;
  labelledBy?: string;
}) {
  return (
    <article className={`nc-course-card ${className}`.trim()} aria-labelledby={labelledBy}>
      <div className="nc-course-card-art" aria-hidden="true">{artwork}</div>
      <div className="nc-course-card-body">{children}</div>
    </article>
  );
}

export function NeetCodeCourseArtwork({ variant }: { variant: NeetCodeCourseArtworkVariant }) {
  const id = useId().replaceAll(":", "");

  if (variant === "learning") {
    return (
      <svg className="nc-course-illustration" viewBox="0 0 360 210" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id={`${id}-path-bg`} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#432574" />
            <stop offset="1" stopColor="#25212d" />
          </linearGradient>
          <linearGradient id={`${id}-path-line`} x1="0" y1="0" x2="1" y2="0">
            <stop stopColor="#b19cff" />
            <stop offset="1" stopColor="#62d0b0" />
          </linearGradient>
        </defs>
        <rect width="360" height="210" fill={`url(#${id}-path-bg)`} />
        <circle cx="285" cy="48" r="74" fill="#8f72ff" opacity=".08" />
        <path d="M38 153 110 101l68 32 72-76 72 39" fill="none" stroke={`url(#${id}-path-line)`} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity=".82" />
        <g fill="#30293b" stroke="#d4caff" strokeWidth="2">
          <circle cx="38" cy="153" r="12" />
          <circle cx="110" cy="101" r="13" />
          <circle cx="178" cy="133" r="12" />
          <circle cx="250" cy="57" r="15" />
          <circle cx="322" cy="96" r="11" />
        </g>
      </svg>
    );
  }

  if (variant === "project") {
    return (
      <svg className="nc-course-illustration" viewBox="0 0 200 170" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id={`${id}-project-bg`} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#52253f" />
            <stop offset="1" stopColor="#29212d" />
          </linearGradient>
        </defs>
        <rect width="200" height="170" fill={`url(#${id}-project-bg)`} />
        <rect x="32" y="25" width="136" height="120" rx="10" fill="#211f27" stroke="#847087" strokeOpacity=".55" />
        <path d="M32 48h136" stroke="#847087" strokeOpacity=".55" />
        <circle cx="45" cy="37" r="3" fill="#f18b91" />
        <circle cx="56" cy="37" r="3" fill="#efc66b" />
        <circle cx="67" cy="37" r="3" fill="#69d2ab" />
        <rect x="48" y="64" width="70" height="7" rx="3.5" fill="#eeeaf5" opacity=".85" />
        <rect x="48" y="80" width="101" height="5" rx="2.5" fill="#8d8496" />
        <rect x="48" y="94" width="79" height="5" rx="2.5" fill="#8d8496" />
        <rect x="48" y="116" width="22" height="5" rx="2.5" fill="#c794ff" opacity=".8" />
        <rect x="76" y="116" width="47" height="5" rx="2.5" fill="#70cdb1" opacity=".7" />
      </svg>
    );
  }

  return (
    <svg className="nc-course-illustration" viewBox="0 0 200 170" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id={`${id}-career-bg`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#34315a" />
          <stop offset="1" stopColor="#25212d" />
        </linearGradient>
      </defs>
      <rect width="200" height="170" fill={`url(#${id}-career-bg)`} />
      <path d="M36 128h42V94h42V61h45" fill="none" stroke="#9c8af1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity=".82" />
      <path d="M78 94V58h42" fill="none" stroke="#70cdb1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity=".68" />
      <g fill="#302b3c" stroke="#c1b3ff" strokeWidth="2">
        <circle cx="36" cy="128" r="10" />
        <circle cx="78" cy="94" r="11" />
        <circle cx="120" cy="61" r="12" />
        <circle cx="165" cy="61" r="10" />
      </g>
    </svg>
  );
}

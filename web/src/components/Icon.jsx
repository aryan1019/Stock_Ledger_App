const paths = {
  logo: <><path d="M3 20h18" /><path d="M6 20V9" /><path d="M11 20V4" /><path d="M16 20v-7" /><path d="M21 20v-11" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  up: <><path d="M12 19V5" /><path d="M5 12l7-7 7 7" /></>,
  down: <><path d="M12 5v14" /><path d="M5 12l7 7 7-7" /></>,
  back: <path d="M15 18l-6-6 6-6" />,
  right: <path d="M9 6l6 6-6 6" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.01" /></>,
  trash: <><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13" /><path d="M9 7V4h6v3" /></>,
  close: <><path d="M6 6l12 12M18 6L6 18" /></>,
}

export default function Icon({ name, size = 16, color = 'currentColor', strokeWidth = 2 }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}

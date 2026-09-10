/**
 * AEW brand hex constants shared by the map, chart and CSS-token layers.
 * Single source of truth so components never hardcode a colour literal.
 */

export const BRAND = {
  blue: "#0065A8",
  navy: "#003B5C",
  blueHover: "#00558C",
  blueLight: "#EAF4FA",
} as const;

export const NEUTRAL = {
  pageBg: "#F5F6F4",
  surfaceSoft: "#F7F9FB",
  borderLight: "#D9E0E6",
  borderMedium: "#C7D0D8",
  textSecondary: "#65727D",
  textPrimary: "#182638",
  textDark: "#102033",
} as const;

export const MAP = {
  background: "#F5F6F4",
  land: "#F7F8F6",
  roadMajor: "#FFFFFF",
  roadMinor: "#E3E5E4",
  water: "#DDE9ED",
  label: "#1F2933",
  plzFill: "#EAF2FA",
  plzBorder: "#AFC2D8",
  plzHover: "#D9E8F6",
} as const;

export const CHART = {
  line: "#18385A",
  grid: "#E1E6EA",
  axis: "#65727D",
} as const;

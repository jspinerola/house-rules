// Capital One-inspired palette and type scale for the fictional Harbor Bank demo.
export const colors = {
  navy: '#0B2A4A',
  navyDeep: '#071C33',
  navySoft: '#173E66',
  red: '#C8102E',
  canvas: '#EEF2F6',
  card: '#FFFFFF',
  ink: '#10202F',
  muted: '#5B6B7B',
  hairline: '#DCE3EA',
  credit: '#1E7F4F',
  creditSoft: '#DFF3E8',
  debitSoft: '#FBE3E6',
};

export const fonts = {
  regular: 'DMSans_400Regular',
  medium: 'DMSans_500Medium',
  bold: 'DMSans_700Bold',
};

export const money = (n: number) =>
  `${n < 0 ? '-' : ''}$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const signedMoney = (n: number) => (n > 0 ? `+${money(n)}` : money(n));

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// "2026-12-16" -> "Dec 16"; dates are plain ISO days, so avoid timezone shifts from Date().
export const shortDate = (iso: string) => {
  const [, m, d] = iso.split('-').map(Number);
  return m && d ? `${MONTHS[m - 1]} ${d}` : iso;
};

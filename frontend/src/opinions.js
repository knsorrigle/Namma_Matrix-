// The five things every citizen has an opinion about (see OPINION_TOPICS in contracts.py).
export const TOPICS = {
  big_companies: { label: 'Big companies', statement: 'Big tech companies coming in is good for people like me.' },
  government: { label: 'Government', statement: 'The government is running the city well.' },
  metro: { label: 'Namma Metro', statement: 'Namma Metro is worth it for people like me.' },
  my_area: { label: 'My area', statement: 'My area is a good place to live.' },
  future_here: { label: 'Future here', statement: 'I see my future in Bengaluru.' },
}

export function stanceWord(s) {
  if (s >= 0.6) return 'strongly agree'
  if (s >= 0.2) return 'agree'
  if (s > -0.2) return 'unsure'
  if (s > -0.6) return 'disagree'
  return 'strongly disagree'
}

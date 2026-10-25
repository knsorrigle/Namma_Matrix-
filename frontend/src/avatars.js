// A little character for each job, shown on the map.
const BY_JOB = {
  'software engineer': '💻',
  'QA tester': '🧪',
  'data analyst': '📊',
  'IT project manager': '📋',
  'night-shift support engineer': '🎧',
  'machine operator': '⚙️',
  'factory supervisor': '🏭',
  'auto driver': '🛺',
  'delivery rider': '🛵',
  nurse: '🩺',
  'school teacher': '📚',
  'darshini owner': '☕',
  'security guard': '🛡️',
  'bank clerk': '🏦',
  'domestic worker': '🧹',
  'kirana shop owner': '🏪',
  'mall sales associate': '🛍️',
  'vegetable vendor': '🥬',
  mason: '🧱',
  'site engineer': '👷',
}

export const avatarFor = (citizen) => BY_JOB[citizen.job] ?? '🙂'

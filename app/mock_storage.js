// Local Storage with lightweight encryption wrapper for synthetic privacy
const STORAGE_KEY = 'asha_saathi_records';

function encryptData(data) {
  return btoa(unescape(encodeURIComponent(JSON.stringify(data))));
}

function decryptData(ciphertext) {
  try {
    return JSON.parse(decodeURIComponent(escape(atob(ciphertext))));
  } catch (e) {
    return [];
  }
}

export function getSavedVisits() {
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw ? decryptData(raw) : [];
}

export function saveVisitRecord(record) {
  const records = getSavedVisits();
  const newRecord = { 
    ...record, 
    id: Date.now(), 
    timestamp: new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) 
  };
  records.push(newRecord);
  localStorage.setItem(STORAGE_KEY, encryptData(records));
  return records;
}

export function clearAllData() {
  localStorage.removeItem(STORAGE_KEY);
}
const state = { assets: [], people: [] };
const $ = (selector) => document.querySelector(selector);
const iconFor = (category) => ({ Electronics: '▣', Vehicle: '▱', Home: '⌂', Subscription: '◌', Equipment: '⚒' }[category] || '◈');
const money = (value) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value || 0);

// Sanitize HTML to prevent XSS
const sanitize = (str) => {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
};

async function loadData() {
  const [assetsResponse, summaryResponse, peopleResponse] = await Promise.all([fetch('/api/assets'), fetch('/api/summary'), fetch('/api/people')]);
  state.assets = await assetsResponse.json();
  state.people = await peopleResponse.json();
  const summary = await summaryResponse.json();
  $('#asset-count').textContent = summary.asset_count;
  $('#asset-nav-count').textContent = summary.asset_count;
  $('#total-value').textContent = money(summary.total_value);
  $('#document-count').textContent = state.assets.filter((asset) => asset.document_name).length;
  renderRecent();
  renderAll();
  renderPeople();
  if (!state.assets.length) {
    const warningCard = document.querySelector('.warning-card > strong');
    const warningText = document.querySelector('.warning-card .warning');
    const reminderList = document.querySelector('.reminder-list');
    const insightH3 = document.querySelector('.insight-banner h3');
    const insightP = document.querySelector('.insight-banner p');
    if (warningCard) warningCard.textContent = '0';
    if (warningText) warningText.textContent = '● No deadlines yet';
    if (reminderList) reminderList.innerHTML = '<p class="empty-copy">No reminders yet. Add an asset with a deadline to see it here.</p>';
    if (insightH3) insightH3.textContent = 'Your workspace is ready for real information';
    if (insightP) insightP.textContent = 'Add your first asset or person to start building your private collection.';
  }
}

async function loadUser() {
  const response = await fetch('/api/me');
  const user = await response.json();
  const profile = document.querySelector('.profile');
  const heading = document.querySelector('.welcome-row h1');
  if (!profile || !heading) return;
  if (user) {
    const avatar = profile.querySelector('.avatar');
    const strong = profile.querySelector('strong');
    const small = profile.querySelector('small');
    if (avatar) avatar.textContent = (user.name || user.email || '?').slice(0, 1).toUpperCase();
    if (strong) strong.textContent = user.name || user.email;
    if (small) small.textContent = user.email || 'Google account';
    heading.innerHTML = `Welcome back, ${sanitize(user.name || 'there')} <span>✦</span>`;
  } else {
    const login = document.createElement('a');
    login.className = 'secondary-button google-login';
    login.href = '/auth/google';
    login.textContent = 'Continue with Google';
    const topActions = document.querySelector('.top-actions');
    if (topActions) topActions.prepend(login);
    heading.innerHTML = 'Keep track of what matters <span>✦</span>';
  }
}

function assetRow(asset) {
  return `<div class="asset-row"><span class="asset-symbol">${iconFor(asset.category)}</span><div class="asset-data"><strong>${sanitize(asset.name)}</strong><small>${sanitize(asset.vendor || asset.category)} · ${asset.document_name ? 'Document attached' : 'No document yet'}</small></div><div class="asset-price"><strong>${money(asset.price)}</strong><small>${asset.purchased_on || 'No date'}</small></div></div>`;
}
function renderRecent() { const elem = $('#recent-assets'); if (elem) elem.innerHTML = state.assets.slice(0, 4).map(assetRow).join(''); }
function renderAll() {
  const query = ($('#asset-search')?.value || '').toLowerCase();
  const elem = $('#all-assets');
  if (elem) elem.innerHTML = state.assets.filter((asset) => `${asset.name} ${asset.vendor} ${asset.category}`.toLowerCase().includes(query)).map((asset) => `<article class="asset-card"><div class="asset-symbol">${iconFor(asset.category)}</div><h3>${sanitize(asset.name)}</h3><p>${sanitize(asset.vendor || 'Personal')} · ${sanitize(asset.category)}</p><div class="asset-card-footer"><strong>${money(asset.price)}</strong><button data-delete="${asset.id}">Archive</button></div></article>`).join('');
}
function renderPeople() {
  const countElem = $('#people-count');
  const listElem = $('#people-list');
  if (countElem) countElem.textContent = state.people.length ? `${state.people.length} ${state.people.length === 1 ? 'person' : 'people'} added` : 'No people added yet';
  if (listElem) listElem.innerHTML = state.people.map((person) => `<article class="person-card"><span class="person-avatar">${sanitize(person.name).slice(0, 1).toUpperCase()}</span><div><h3>${sanitize(person.name)}</h3><p>${sanitize(person.role || 'No role or relationship added')}</p>${person.email ? `<small>${sanitize(person.email)}</small>` : ''}${person.phone ? `<small>${sanitize(person.phone)}</small>` : ''}</div><button data-delete-person="${person.id}">Remove</button></article>`).join('');
}
function showView(view) {
  const overview = $('#overview-view'); const assets = $('#assets-view'); const people = $('#people-view');
  if (overview) overview.classList.toggle('hidden', view !== 'overview');
  if (assets) assets.classList.toggle('hidden', view !== 'assets');
  if (people) people.classList.toggle('hidden', view !== 'people');
  const pageTitle = $('#page-title');
  if (pageTitle) pageTitle.textContent = view === 'assets' ? 'My assets' : view === 'people' ? 'People' : 'Overview';
  document.querySelectorAll('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
  if (view === 'assets') renderAll();
  if (view === 'people') renderPeople();
}
function openModal() { const modal = $('#import-modal'); if (modal) modal.classList.remove('hidden'); }
function closeModal() { const modal = $('#import-modal'); if (modal) modal.classList.add('hidden'); const status = $('#form-status'); if (status) status.textContent = ''; const form = $('#upload-form'); if (form) form.reset(); }

document.addEventListener('click', async (event) => {
  const viewButton = event.target.closest('[data-view]');
  if (viewButton) showView(viewButton.dataset.view);
  if (event.target.closest('#add-button') || event.target.closest('#assets-add-button') || event.target.closest('#import-button')) openModal();
  if (event.target.closest('#close-modal')) closeModal();
  const deleteButton = event.target.closest('[data-delete]');
  if (deleteButton) { await fetch(`/api/assets/${deleteButton.dataset.delete}`, { method: 'DELETE' }); await loadData(); }
  const deletePerson = event.target.closest('[data-delete-person]');
  if (deletePerson) { await fetch(`/api/people/${deletePerson.dataset.deletePerson}`, { method: 'DELETE' }); await loadData(); }
});
$('#upload-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const status = $('#form-status'); status.textContent = 'Reading your document…';
  const response = await fetch('/api/import', { method: 'POST', body: new FormData(event.target) });
  if (!response.ok) { status.textContent = 'Could not import that document.'; return; }
  const result = await response.json(); status.textContent = `Added ${result.asset.name} with ${result.extracted.length} extracted fields.`;
  await loadData(); setTimeout(closeModal, 1100);
});
$('#asset-search').addEventListener('input', renderAll);
$('#person-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const status = $('#person-status'); const payload = Object.fromEntries(new FormData(event.target));
  const response = await fetch('/api/people', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) { status.textContent = 'Please enter a name.'; return; }
  event.target.reset(); status.textContent = 'Person saved.'; await loadData();
});
$('#person-add-button').addEventListener('click', () => document.querySelector('#person-form input[name="name"]')?.focus());
loadData();
loadUser();

// SmartFinance AI - Complete Application Logic
const API_BASE = '/api';

// Global State
let currentTab = 'overview';
let netWorthData = null;
let accountsList = [];
let creditCardsList = [];
let loansList = [];
let simulationData = null;
let categoriesList = [];
let turkishBanksList = [];
let pendingNLPResult = null;

// Core & Advanced Modules State
let categoryBudgetsList = [];
let subscriptionsData = null;
let psychologyData = null;
let personalInflationData = null;
let whatIfSimulationData = null;
let isMetricsAccordionExpanded = false;

// User Authentication State
let currentUser = JSON.parse(localStorage.getItem('smartfin_user') || 'null');
let authToken = localStorage.getItem('smartfin_token') || '';

// Chart Instances
let cashFlowChartInstance = null;
let categoryChartInstance = null;

// ==========================================
// INITIALIZATION
// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
  syncInstallButtonsVisibility();
  if (window.matchMedia) {
    window.matchMedia('(display-mode: standalone)').addEventListener('change', syncInstallButtonsVisibility);
  }
  initDateDefaults();
  await loadTurkishBanks();
  await loadCategories();
  
  const isAuthenticated = await checkAndRestoreAuth();
  if (isAuthenticated) {
    await refreshAllData();
    await pollAndDisplayNotifications();
  }
  syncInstallButtonsVisibility();
  initAutoSyncListeners();

  if (window.lucide) {
    lucide.createIcons();
  }
});

function isAppInstalled() {
  const isStandalone = window.matchMedia && window.matchMedia('(display-mode: standalone)').matches;
  const isIOSStandalone = window.navigator.standalone === true;
  const isMarkedInstalled = localStorage.getItem('smartfin_pwa_installed') === 'true';
  return isStandalone || isIOSStandalone || isMarkedInstalled;
}

function syncInstallButtonsVisibility() {
  const installed = isAppInstalled();
  const headerInstallBtn = document.getElementById('btn-app-install-header');
  const sidebarInstallBtn = document.getElementById('sidebar-install-btn');

  if (installed) {
    if (headerInstallBtn) headerInstallBtn.style.display = 'none';
    if (sidebarInstallBtn) sidebarInstallBtn.style.display = 'none';
  } else {
    if (headerInstallBtn) headerInstallBtn.style.display = '';
    if (sidebarInstallBtn) sidebarInstallBtn.style.display = '';
  }
}

function setAuthScreenState(authenticated) {
  const authModal = document.getElementById('modal-auth');
  const appShell = document.getElementById('app-shell');

  if (authenticated) {
    document.documentElement.classList.add('has-auth');
    if (authModal) {
      authModal.classList.add('hidden');
      authModal.classList.remove('flex');
    }
    if (appShell) {
      appShell.classList.remove('hidden');
      appShell.classList.add('flex');
    }
  } else {
    document.documentElement.classList.remove('has-auth');
    if (appShell) {
      appShell.classList.add('hidden');
      appShell.classList.remove('flex');
    }
    if (authModal) {
      authModal.classList.remove('hidden');
      authModal.classList.add('flex');
    }
    clearClientState();
  }
}

function clearClientState() {
  accountsList = [];
  creditCardsList = [];
  loansList = [];
  netWorthData = null;
  simulationData = null;
  categoryBudgetsList = [];
  subscriptionsData = null;
  psychologyData = null;
  personalInflationData = null;
  whatIfSimulationData = null;

  // Reset metric figures so no previous numbers remain in DOM
  const elNetWorth = document.getElementById('metric-net-worth');
  if (elNetWorth) elNetWorth.textContent = '0 ₺';
  const elAssets = document.getElementById('metric-assets-total');
  if (elAssets) elAssets.textContent = 'Varlık: 0 ₺';
  const elLiabilities = document.getElementById('metric-liabilities-total');
  if (elLiabilities) elLiabilities.textContent = 'Borç: 0 ₺';
  const elLiquid = document.getElementById('metric-liquid-cash');
  if (elLiquid) elLiquid.textContent = '0 ₺';
  const elCardsDebt = document.getElementById('metric-cc-debt');
  if (elCardsDebt) elCardsDebt.textContent = '0 ₺';
  const elLoansDebt = document.getElementById('metric-loan-debt');
  if (elLoansDebt) elLoansDebt.textContent = '0 ₺';
  const elSidebarNetWorth = document.getElementById('sidebar-net-worth');
  if (elSidebarNetWorth) elSidebarNetWorth.textContent = '0 ₺';
  const elHeroDaily = document.getElementById('hero-daily-budget');
  if (elHeroDaily) elHeroDaily.textContent = '0 ₺ / gün';

  if (typeof renderOverviewCards === 'function') renderOverviewCards();
  if (typeof renderAccountsList === 'function') renderAccountsList();
  if (typeof renderCreditCards === 'function') renderCreditCards();
  if (typeof renderLoansList === 'function') renderLoansList();
  if (typeof renderCreditAnalytics === 'function') renderCreditAnalytics();
  if (typeof renderSimulationUI === 'function') renderSimulationUI();
  if (typeof renderCategoryBudgetsUI === 'function') renderCategoryBudgetsUI();
  if (typeof renderSubscriptionHunterUI === 'function') renderSubscriptionHunterUI();
  if (typeof renderSpendingPsychologyUI === 'function') renderSpendingPsychologyUI();
  if (typeof renderPersonalInflationUI === 'function') renderPersonalInflationUI();
}

async function checkAndRestoreAuth() {
  // Support 1-click instant login via URL token (e.g. ?token=...)
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const magicToken = urlParams.get('token');
    if (magicToken && magicToken.length >= 16) {
      authToken = magicToken;
      localStorage.setItem('smartfin_token', authToken);
      if (window.history && window.history.replaceState) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }
  } catch (paramErr) {
    console.warn('URL token parse notice:', paramErr);
  }

  if (authToken) {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (res.ok) {
        currentUser = await res.json();
        localStorage.setItem('smartfin_user', JSON.stringify(currentUser));
        setAuthScreenState(true);
        updateAuthUI();
        return true;
      } else if (res.status === 401 || res.status === 403) {
        // Token expired or invalid
        authToken = '';
        currentUser = null;
        localStorage.removeItem('smartfin_token');
        localStorage.removeItem('smartfin_user');
      }
    } catch (e) {
      // Offline network catch: If PC is off and user is in offline mode with cached credentials, preserve session!
      if (currentUser && authToken) {
        setAuthScreenState(true);
        updateAuthUI();
        return true;
      }
      console.warn('Auth check warning:', e);
      authToken = '';
      currentUser = null;
      localStorage.removeItem('smartfin_token');
      localStorage.removeItem('smartfin_user');
    }
  }
  setAuthScreenState(false);
  updateAuthUI();
  return false;
}

function initDateDefaults() {
  const todayStr = new Date().toISOString().split('T')[0];
  const manualDate = document.getElementById('manual-date');
  if (manualDate) manualDate.value = todayStr;
}

// ==========================================
// OFFLINE-FIRST MOBILE ENGINE & CACHE SYNC
// Allows full mobile app usage even when PC is turned off
// ==========================================
let isOfflineMode = false;
let offlineQueue = JSON.parse(localStorage.getItem('smartfin_offline_queue') || '[]');

function setOfflineMode(active) {
  if (isOfflineMode === active) return;
  isOfflineMode = active;
  const banner = document.getElementById('offline-banner');
  if (banner) {
    if (isOfflineMode) {
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
  }
  if (window.lucide) lucide.createIcons();
}

function queueOfflineAction(url, options) {
  const item = {
    id: Date.now(),
    url,
    method: options.method || 'POST',
    body: options.body || null,
    headers: options.headers || {},
    timestamp: new Date().toISOString()
  };
  offlineQueue.push(item);
  localStorage.setItem('smartfin_offline_queue', JSON.stringify(offlineQueue));
  showToast('💾 İşlem telefonunuza çevrimdışı kaydedildi. Bağlantı kurulduğunda senkronize edilecektir.', '📱');
}

async function syncOfflineQueue() {
  if (!offlineQueue.length || !navigator.onLine) return;
  const queueToSync = [...offlineQueue];
  offlineQueue = [];
  localStorage.setItem('smartfin_offline_queue', JSON.stringify([]));
  
  let successCount = 0;
  for (const item of queueToSync) {
    try {
      const headers = item.headers || {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      const res = await fetch(item.url, {
        method: item.method,
        headers,
        body: item.body
      });
      if (res.ok) successCount++;
    } catch (e) {
      offlineQueue.push(item);
      localStorage.setItem('smartfin_offline_queue', JSON.stringify(offlineQueue));
    }
  }
  if (successCount > 0) {
    showToast(`✅ ${successCount} adet çevrimdışı işlem sunucuya aktarıldı!`, '🔄');
    refreshAllData();
  }
}

window.addEventListener('online', () => {
  setOfflineMode(false);
  syncOfflineQueue();
  refreshAllData();
});

window.addEventListener('offline', () => {
  setOfflineMode(true);
});

// Helper for authenticated requests with auto-logout on 401 & offline fallback
async function authFetch(url, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  const method = (options.method || 'GET').toUpperCase();
  const cacheKey = `smartfin_cache_${url}`;
  
  try {
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
      authToken = '';
      currentUser = null;
      localStorage.removeItem('smartfin_token');
      localStorage.removeItem('smartfin_user');
      updateAuthUI();
      clearClientState();
      openModal('modal-auth');
      return res;
    }
    
    // On successful GET, cache data in localStorage for offline access
    if (method === 'GET' && res.ok) {
      const clone = res.clone();
      clone.text().then(text => {
        try {
          localStorage.setItem(cacheKey, text);
        } catch (e) {}
      });
      if (isOfflineMode) {
        setOfflineMode(false);
        syncOfflineQueue();
      }
    }
    return res;
  } catch (networkErr) {
    // Network failed (e.g. computer is off, no WiFi, or tunnel down)
    console.warn(`[OfflineMode] Network unreachable for ${url}, fallback to client storage.`);
    setOfflineMode(true);
    
    if (method === 'GET') {
      const cached = localStorage.getItem(cacheKey);
      if (cached) {
        return new Response(cached, {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
      }
    } else {
      // POST, PUT, DELETE: queue for later sync and return mock success so UI continues
      queueOfflineAction(url, options);
      return new Response(JSON.stringify({ success: true, offline: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    throw networkErr;
  }
}

// ==========================================
// REAL-TIME AUTO-SYNC & NOTIFICATIONS ENGINE
// ==========================================
let isRefreshingData = false;
let autoSyncIntervalTimer = null;

async function refreshAllData(silent = false) {
  if (!authToken || isRefreshingData) {
    if (!authToken) clearClientState();
    return;
  }
  isRefreshingData = true;
  try {
    await Promise.all([
      loadNetWorthAndAccounts(),
      loadCreditsAndLoans(),
      loadSimulation(),
      loadTransactions(),
      loadRecurringItems(),
      loadMonthlyComparison(),
      loadAIChatHistory(),
      loadCategoryBudgets(),
      loadSubscriptionHunter(),
      loadSpendingPsychology(),
      loadPersonalInflation()
    ]);
  } catch (err) {
    if (!silent) console.error('Data load error:', err);
  } finally {
    isRefreshingData = false;
  }
}

// Notification Engine
function updateNotificationButtonState() {
  const btn = document.getElementById('btn-toggle-notifications');
  const label = document.getElementById('btn-notif-label');
  if (!btn) return;

  if (!('Notification' in window)) {
    btn.style.display = 'none';
    return;
  }

  if (Notification.permission === 'granted') {
    btn.className = "px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 transition-all flex items-center gap-1.5 shadow-sm";
    btn.title = "Bildirimler Aktif";
    if (label) label.textContent = "Bildirimler Aktif";
  } else if (Notification.permission === 'denied') {
    btn.className = "px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30 transition-all flex items-center gap-1.5 shadow-sm";
    btn.title = "Bildirim İzni Reddedildi (Tarayıcı ayarlarından açabilirsiniz)";
    if (label) label.textContent = "Bildirim Kapalı";
  } else {
    btn.className = "px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 border border-amber-500/30 transition-all flex items-center gap-1.5 shadow-sm animate-pulse";
    btn.title = "Bildirimleri Aç (Para girişi ve borç kapanmalarında anında haber ver)";
    if (label) label.textContent = "Bildirimleri Aç";
  }
}

async function toggleNotificationSubscription() {
  if (!('Notification' in window)) {
    alert("Cihazınız veya tarayıcınız Web Bildirimlerini desteklemiyor.");
    return;
  }

  if (Notification.permission === 'granted') {
    // Send a test notification
    try {
      await apiRequest('/notifications/test', 'POST');
      await pollAndDisplayNotifications();
    } catch (e) {
      showPhoneNotification("Finans Koçun", "Bildirim sisteminiz aktif ve çalışıyor!");
    }
  } else {
    const perm = await Notification.requestPermission();
    updateNotificationButtonState();
    if (perm === 'granted') {
      showPhoneNotification("Finans Koçun", "🎉 Bildirimler başarıyla açıldı! Para girişleri ve borç ödemeleri anında bildirilecektir.");
    }
  }
}

async function showPhoneNotification(title, message, notifType = 'info') {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;

  try {
    if (navigator.serviceWorker && navigator.serviceWorker.ready) {
      const reg = await navigator.serviceWorker.ready;
      if (reg && reg.showNotification) {
        reg.showNotification(title, {
          body: message,
          icon: '/static/icon-192.png',
          badge: '/static/icon-192.png',
          vibrate: [150, 75, 150],
          tag: 'finanskocun-' + Date.now(),
          renotify: true,
          data: { url: '/' }
        });
        return;
      }
    }
  } catch (swErr) {
    console.warn("ServiceWorker showNotification fallback:", swErr);
  }

  try {
    new Notification(title, {
      body: message,
      icon: '/static/icon-192.png'
    });
  } catch (notifErr) {
    console.warn("Desktop Notification fallback:", notifErr);
  }
}

async function pollAndDisplayNotifications() {
  if (!authToken) return;
  try {
    const unread = await apiRequest('/notifications/unread', 'GET');
    if (unread && Array.isArray(unread) && unread.length > 0) {
      for (const item of unread) {
        showPhoneNotification(item.title, item.message, item.type);
        if (typeof showToast === 'function') {
          showToast(`${item.title}: ${item.message}`);
        }
      }
    }
  } catch (e) {
    // Silent on background poll
  }
}

let autoSyncInitialized = false;
function initAutoSyncListeners() {
  if (autoSyncInitialized) return;
  autoSyncInitialized = true;

  updateNotificationButtonState();

  // 1. Mobile phone resume / Tab visibility change (Auto-update when switching back to app)
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'visible' && authToken) {
      await refreshAllData(true);
      await pollAndDisplayNotifications();
    }
  });

  // 2. Window focus
  window.addEventListener('focus', async () => {
    if (authToken) {
      await refreshAllData(true);
      await pollAndDisplayNotifications();
    }
  });

  // 3. Background periodic sync (every 6 seconds so user NEVER needs to log out)
  if (autoSyncIntervalTimer) clearInterval(autoSyncIntervalTimer);
  autoSyncIntervalTimer = setInterval(async () => {
    if (authToken && document.visibilityState === 'visible') {
      await refreshAllData(true);
      await pollAndDisplayNotifications();
    }
  }, 6000);
}


// ==========================================
// USER AUTHENTICATION & LOGIN/LOGOUT
// ==========================================
function updateAuthUI() {
  const badgeContainer = document.getElementById('user-auth-badge');
  const navAdmin = document.getElementById('nav-admin');
  const sidebarPlanBadge = document.getElementById('sidebar-plan-badge');

  const currentPlan = (currentUser?.plan || 'free').toLowerCase();

  if (sidebarPlanBadge) {
    sidebarPlanBadge.textContent = currentPlan.toUpperCase();
    if (currentPlan === 'vip') {
      sidebarPlanBadge.className = 'text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1.5 py-0.5 rounded-md font-mono font-bold tracking-wider uppercase';
    } else if (currentPlan === 'pro') {
      sidebarPlanBadge.className = 'text-[9px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.5 rounded-md font-mono font-bold tracking-wider uppercase';
    } else {
      sidebarPlanBadge.className = 'text-[9px] bg-white/10 text-gray-400 border border-white/10 px-1.5 py-0.5 rounded-md font-mono font-bold tracking-wider uppercase';
    }
  }

  if (navAdmin) {
    if (currentUser && currentUser.is_admin) {
      navAdmin.classList.remove('hidden');
    } else {
      navAdmin.classList.add('hidden');
    }
  }

  if (!badgeContainer) return;

  if (currentUser) {
    let planTag = '';
    if (currentPlan === 'vip') {
      planTag = `<span class="ml-1.5 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[9px] font-bold border border-amber-500/30 font-mono">👑 VIP</span>`;
    } else if (currentPlan === 'pro') {
      planTag = `<span class="ml-1.5 px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[9px] font-bold border border-emerald-500/30 font-mono">⭐ PRO</span>`;
    } else {
      planTag = `<span class="ml-1.5 px-1.5 py-0.5 rounded bg-white/10 text-gray-300 text-[9px] font-semibold border border-white/10 font-mono">FREE</span>`;
    }

    const adminTag = currentUser.is_admin 
      ? `<span class="ml-1 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[9px] font-bold border border-amber-500/30">ADMİN</span>` 
      : '';

    badgeContainer.innerHTML = `
      <div class="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-xl text-xs">
        <div class="w-6 h-6 rounded-full ${currentUser.is_admin ? 'bg-amber-500/30 text-amber-300 border border-amber-500/40' : 'bg-indigo-600/40 text-indigo-300'} flex items-center justify-center font-bold text-[11px]">
          ${currentUser.full_name ? currentUser.full_name.charAt(0).toUpperCase() : 'U'}
        </div>
        <div class="hidden sm:block text-left">
          <div class="flex items-center">
            <span class="font-bold text-white block text-[11px] leading-tight">${currentUser.full_name}</span>
            ${planTag}
            ${adminTag}
          </div>
          <span class="text-[9px] text-gray-400 block leading-none">${currentUser.email}</span>
        </div>
        <button onclick="openPricingModal()" title="Paketimi Yükselt" class="ml-1 p-1 text-amber-400/80 hover:text-amber-300 transition">
          <i data-lucide="crown" class="w-3.5 h-3.5"></i>
        </button>
        <button onclick="handleZeroResetConfirm()" title="Tüm rakamları sıfırla" class="p-1 text-gray-400 hover:text-amber-400 transition">
          <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
        </button>
        <button onclick="handleLogout()" title="Çıkış Yap" class="p-1 text-gray-400 hover:text-rose-400 transition">
          <i data-lucide="log-out" class="w-3.5 h-3.5"></i>
        </button>
      </div>
    `;
  } else {
    badgeContainer.innerHTML = `
      <button onclick="openModal('modal-auth')" class="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-md shadow-indigo-600/30 transition flex items-center gap-1.5">
        <i data-lucide="user" class="w-3.5 h-3.5"></i>
        <span>Giriş Yap / Kayıt Ol</span>
      </button>
      <button onclick="handleZeroResetConfirm()" title="Rakamları Sıfırla" class="p-1.5 rounded-xl text-xs text-gray-400 hover:text-amber-400 bg-white/5 border border-white/10 transition">
        <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
      </button>
    `;
  }

  if (window.lucide) lucide.createIcons();
}

let authMode = 'login';
function setAuthTab(mode) {
  authMode = mode;
  const btnLogin = document.getElementById('btn-auth-tab-login');
  const btnRegister = document.getElementById('btn-auth-tab-register');
  const fieldName = document.getElementById('auth-field-name');
  const modalTitle = document.getElementById('auth-modal-title');
  const modalSubtitle = document.getElementById('auth-modal-subtitle');
  const submitBtn = document.getElementById('auth-submit-btn');
  const passHint = document.getElementById('auth-pass-hint');
  const errEl = document.getElementById('auth-error-msg');
  if (errEl) errEl.classList.add('hidden');

  if (mode === 'login') {
    btnLogin.className = 'py-2 rounded-lg font-bold bg-indigo-600 text-white transition shadow-sm';
    btnRegister.className = 'py-2 rounded-lg font-bold text-gray-400 hover:text-white transition';
    fieldName.classList.add('hidden');
    modalTitle.textContent = 'Hesabınıza Giriş Yapın';
    if (modalSubtitle) modalSubtitle.textContent = 'Finansal asistanınıza erişmek için bilgilerinizi girin';
    submitBtn.innerHTML = `<span>Giriş Yap</span><i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>`;
    if (passHint) passHint.textContent = '';
  } else {
    btnRegister.className = 'py-2 rounded-lg font-bold bg-indigo-600 text-white transition shadow-sm';
    btnLogin.className = 'py-2 rounded-lg font-bold text-gray-400 hover:text-white transition';
    fieldName.classList.remove('hidden');
    modalTitle.textContent = 'Yeni Hesap Oluşturun';
    if (modalSubtitle) modalSubtitle.textContent = 'Verilerinizin kalıcı olarak saklanması için ücretsiz kaydolun';
    submitBtn.innerHTML = `<span>Hesap Oluştur ve Başla</span><i data-lucide="sparkles" class="w-3.5 h-3.5 text-amber-300"></i>`;
    if (passHint) passHint.textContent = 'En az 4 karakter';
  }
  if (window.lucide) lucide.createIcons();
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPass = input.type === 'password';
  input.type = isPass ? 'text' : 'password';
  btn.innerHTML = `<i data-lucide="${isPass ? 'eye-off' : 'eye'}" class="w-4 h-4"></i>`;
  if (window.lucide) lucide.createIcons();
}

async function continueAsGuest() {
  await handleDemoLogin();
}

async function handleDemoLogin() {
  const errEl = document.getElementById('auth-error-msg');
  const errText = document.getElementById('auth-error-text');
  if (errEl) errEl.classList.add('hidden');

  try {
    const res = await fetch(`${API_BASE}/auth/demo`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      if (errText) errText.textContent = data.detail || 'Demo girişi başarısız';
      if (errEl) errEl.classList.remove('hidden');
      return;
    }

    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem('smartfin_token', authToken);
    localStorage.setItem('smartfin_user', JSON.stringify(currentUser));

    setAuthScreenState(true);
    updateAuthUI();
    showToast(`Hoş geldiniz, ${currentUser.full_name}! (İzole Test Hesabı)`, '🚀');
    await refreshAllData();
  } catch (err) {
    console.error('Demo auth error:', err);
    if (errText) errText.textContent = 'Sunucu bağlantı hatası oluştu.';
    if (errEl) errEl.classList.remove('hidden');
  }
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const fullName = document.getElementById('auth-name').value.trim();
  const errEl = document.getElementById('auth-error-msg');
  const errText = document.getElementById('auth-error-text');
  if (errEl) errEl.classList.add('hidden');

  const endpoint = authMode === 'login' ? `${API_BASE}/auth/login` : `${API_BASE}/auth/register`;
  const body = authMode === 'login' ? { email, password } : { email, password, full_name: fullName };

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    const data = await res.json();
    if (!res.ok) {
      const msg = data.detail || 'Bir hata oluştu.';
      if (errText) errText.textContent = msg;
      if (errEl) errEl.classList.remove('hidden');
      return;
    }

    // Save auth session permanently
    authToken = data.token;
    currentUser = data.user;
    localStorage.setItem('smartfin_token', authToken);
    localStorage.setItem('smartfin_user', JSON.stringify(currentUser));

    setAuthScreenState(true);
    updateAuthUI();
    showToast(`Hoş geldiniz, ${currentUser.full_name}! Tüm verileriniz güvende.`, '👋');
    await refreshAllData();
  } catch (err) {
    console.error('Auth error:', err);
    if (errText) errText.textContent = 'Sunucu bağlantı hatası oluştu.';
    if (errEl) errEl.classList.remove('hidden');
  }
}

async function handleLogout() {
  if (authToken) {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
    } catch (e) {}
  }
  authToken = '';
  currentUser = null;
  localStorage.removeItem('smartfin_token');
  localStorage.removeItem('smartfin_user');
  sessionStorage.removeItem('smartfin_guest_dismissed');
  setAuthScreenState(false);
  updateAuthUI();
  clearClientState();
  showToast('Oturum kapatıldı.', '🔒');
}


async function handleZeroResetConfirm() {
  if (confirm('Tüm bakiyeler, banka hesapları, kartlar ve harcamalar SIFIRLANSIN mı?\n(Bu işlem tüm rakamları 0.00 ₺ yapacaktır.)')) {
    try {
      const res = await authFetch(`${API_BASE}/auth/reset-data`, { method: 'POST' });
      if (res.ok) {
        showToast('Tüm rakamlar sıfırlandı! Tertemiz bir başlangıç.', '🔄');
        await refreshAllData();
      }
    } catch (err) {
      console.error('Reset error:', err);
    }
  }
}

// ==========================================
// TURKISH BANKS CATALOG (TÜM BANKALAR)
// ==========================================
async function loadTurkishBanks() {
  try {
    const res = await fetch(`${API_BASE}/banks`);
    turkishBanksList = await res.json();

    const accSelect = document.getElementById('acc-bank-select');
    const cardSelect = document.getElementById('card-bank-select');
    const loanSelect = document.getElementById('loan-bank-select');

    const options = turkishBanksList.map(b => `<option value="${b.name}" data-code="${b.code}">${b.name}</option>`).join('');

    if (accSelect) accSelect.innerHTML = options;
    if (cardSelect) cardSelect.innerHTML = options;
    if (loanSelect) loanSelect.innerHTML = options;
  } catch (err) {
    console.error('Error loading banks:', err);
  }
}

function onAccountBankSelectChange(val) {
  const customGroup = document.getElementById('acc-custom-bank-group');
  if (val.includes('Diğer')) {
    customGroup.classList.remove('hidden');
  } else {
    customGroup.classList.add('hidden');
  }
}

function onCardBankSelectChange(val) {
  const customGroup = document.getElementById('card-custom-bank-group');
  if (val.includes('Diğer')) {
    customGroup.classList.remove('hidden');
  } else {
    customGroup.classList.add('hidden');
  }
}

// ==========================================
// NAVIGATION & TABS
// ==========================================
function switchTab(tabId) {
  currentTab = tabId;

  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));

  const target = document.getElementById(`tab-${tabId}`);
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('fade-in');
  }

  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('bg-indigo-600/10', 'text-indigo-400', 'border', 'border-indigo-500/20');
    btn.classList.add('text-gray-300');
  });

  const activeBtn = document.getElementById(`nav-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.remove('text-gray-300');
    activeBtn.classList.add('bg-indigo-600/10', 'text-indigo-400', 'border', 'border-indigo-500/20');
  }

  // Sync mobile bottom navigation items
  ['overview', 'transactions', 'simulation', 'credits', 'ai-coach'].forEach(t => {
    const mobBtn = document.getElementById(`mob-nav-${t}`);
    if (mobBtn) {
      if (t === tabId) {
        mobBtn.classList.remove('text-gray-400');
        mobBtn.classList.add('text-indigo-400', 'font-bold');
      } else {
        mobBtn.classList.remove('text-indigo-400', 'font-bold');
        mobBtn.classList.add('text-gray-400');
      }
    }
  });

  const titleEl = document.getElementById('header-page-title');
  const subEl = document.getElementById('header-page-subtitle');
  if (tabId === 'overview') {
    titleEl.textContent = 'Genel Bakış & Net Değer';
    subEl.textContent = 'Finansal varlıkların ve nakit akışının anlık durumu';
  } else if (tabId === 'simulation') {
    titleEl.textContent = 'Ay Sonu Simülasyonu';
    subEl.textContent = 'Ay sonunu çıkartabilecek miyim? Nakit akışı ve likidite öngörüsü';
    setTimeout(renderCashFlowChart, 100);
  } else if (tabId === 'credits') {
    titleEl.textContent = 'Kartlar & Krediler';
    subEl.textContent = 'Kredi kartı ekstre ve son ödeme tarihleri, taksit takibi';
  } else if (tabId === 'transactions') {
    titleEl.textContent = 'Gelir & Giderler';
    subEl.textContent = 'Günlük harcamalar ve aylık düzenli bütçe kuralları';
  } else if (tabId === 'ai-coach') {
    titleEl.textContent = 'Finans Koçun';
    subEl.textContent = 'Bütçe alışkanlıklarınızı analiz eden akıllı finansal asistan';
    scrollAIChatToBottom();
  } else if (tabId === 'admin') {
    if (!currentUser || !currentUser.is_admin) {
      showToast('Bu ekrana yalnızca Sistem Yöneticisi erişebilir.', '⚠️');
      switchTab('overview');
      return;
    }
    titleEl.textContent = 'Sistem Yönetim & Finansal Denetim Portalı';
    subEl.textContent = 'Platformdaki tüm kayıtlı kullanıcıların varlık ve borç durumunu tek ekrandan denetleyin';
    loadAdminDashboard();
  }


  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('mobile-backdrop');
  if (sidebar && !sidebar.classList.contains('-translate-x-full') && window.innerWidth < 1024) {
    toggleSidebar();
  }

  if (window.lucide) lucide.createIcons();
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('mobile-backdrop');
  if (sidebar) sidebar.classList.toggle('-translate-x-full');
  if (backdrop) backdrop.classList.toggle('hidden');
}

// ==========================================
// 1. ACCOUNTS & NET WORTH (MODULE 1)
// ==========================================
async function loadNetWorthAndAccounts() {
  try {
    const [nwRes, accRes] = await Promise.all([
      authFetch(`${API_BASE}/accounts/net-worth`),
      authFetch(`${API_BASE}/accounts`)
    ]);

    netWorthData = await nwRes.json();
    accountsList = await accRes.json();

    document.getElementById('metric-net-worth').textContent = formatTRY(netWorthData.total_net_worth_try);
    document.getElementById('metric-liquid-cash').textContent = formatTRY(netWorthData.total_liquid_cash_try);
    document.getElementById('metric-cc-debt').textContent = formatTRY(netWorthData.total_credit_debt_try);
    document.getElementById('metric-loan-debt').textContent = formatTRY(netWorthData.total_loan_debt_try);

    const totalAssets = netWorthData.total_liquid_cash_try + netWorthData.total_investment_try;
    document.getElementById('metric-assets-total').textContent = `Varlık: ${formatTRY(totalAssets)}`;
    document.getElementById('metric-liabilities-total').textContent = `Borç: ${formatTRY(netWorthData.total_liabilities_try)}`;

    document.getElementById('sidebar-net-worth').textContent = formatTRY(netWorthData.total_net_worth_try);

    renderAccountsGrid();
  } catch (err) {
    console.error('Error loading accounts:', err);
  }
}

function renderAccountsGrid() {
  const container = document.getElementById('accounts-grid');
  if (!container) return;

  if (accountsList.length === 0) {
    container.innerHTML = `
      <div class="col-span-3 glass-panel p-6 rounded-2xl text-center border-dashed border-white/20">
        <div class="w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 mx-auto flex items-center justify-center mb-3">
          <i data-lucide="landmark" class="w-6 h-6"></i>
        </div>
        <h4 class="text-sm font-bold text-white">Henüz Kayıtlı Banka Hesabı Yok</h4>
        <p class="text-xs text-gray-400 mt-1 max-w-sm mx-auto">Vadesiz banka hesaplarınızı, nakit cüzdanınızı veya döviz/altın varlıklarınızı ekleyerek başlayın.</p>
        <button onclick="openModal('modal-account')" class="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition inline-flex items-center gap-1.5">
          <i data-lucide="plus" class="w-4 h-4"></i>
          <span>İlk Banka Hesabını Ekle</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = accountsList.map(acc => {
    const isLiquid = acc.is_active_cash === 1;
    const badgeHtml = isLiquid
      ? `<span class="text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-semibold">Aktif Nakit</span>`
      : `<span class="text-[10px] bg-purple-500/20 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-full font-semibold">Yatırım</span>`;

    const iconName = acc.icon || 'landmark';

    return `
      <div class="glass-panel p-4 rounded-2xl glass-card-interactive flex flex-col justify-between">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white shrink-0" style="color: ${acc.color || '#fff'}">
              <i data-lucide="${iconName}" class="w-5 h-5"></i>
            </div>
            <div>
              <h4 class="text-xs font-bold text-white">${acc.name}</h4>
              <p class="text-[11px] text-gray-400">${acc.bank_name || 'Banka Hesabı'}</p>
            </div>
          </div>
          <div class="flex items-center gap-1.5">
            ${badgeHtml}
            <button onclick="promptDeleteAccount(${acc.id}, '${acc.name}')" title="Hesabı Sil" class="p-1 rounded-lg text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 transition">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>

        <div class="mt-4 pt-3 border-t border-white/5 flex items-baseline justify-between">
          <div>
            <span class="text-xs text-gray-400 block text-[10px]">Bakiye</span>
            <span class="text-base font-extrabold text-white font-mono">${formatCurrency(acc.balance, acc.currency)}</span>
          </div>
          <div class="flex items-center gap-2">
            ${acc.currency !== 'TRY' ? `
              <div class="text-right">
                <span class="text-[10px] text-gray-500 block">TL Karşılığı</span>
                <span class="text-xs font-semibold text-emerald-400 font-mono">≈ ${formatTRY(acc.balance_try)}</span>
              </div>
            ` : ''}
            <button onclick="promptEditAccountBalance(${acc.id}, '${acc.name}', ${acc.balance})" title="Bakiyeyi Güncelle" class="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white transition text-[11px] flex items-center gap-1">
              <i data-lucide="edit-2" class="w-3 h-3"></i>
              <span>Bakiye</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

// ==========================================
// 2. CREDIT CARDS & LOANS (MODULE 3 - TIMING TRACKING)
// ==========================================
async function loadCreditsAndLoans() {
  try {
    const [cardsRes, loansRes] = await Promise.all([
      authFetch(`${API_BASE}/credits/cards`),
      authFetch(`${API_BASE}/credits/loans`)
    ]);

    creditCardsList = await cardsRes.json();
    loansList = await loansRes.json();

    const totalLoanInstallments = loansList.reduce((acc, l) => acc + l.monthly_installment, 0);
    const loanInstEl = document.getElementById('metric-loan-installment-info');
    if (loanInstEl) {
      loanInstEl.textContent = totalLoanInstallments > 0 ? `Aylık toplam taksit: ${formatTRY(totalLoanInstallments)}` : 'Aylık taksit: 0 ₺';
    }

    const nextCard = creditCardsList[0];
    const ccDueEl = document.getElementById('metric-cc-due-info');
    if (ccDueEl) {
      if (nextCard) {
        ccDueEl.textContent = `En yakın: ${nextCard.bank_name} (${nextCard.days_until_due} gün kaldı)`;
      } else {
        ccDueEl.textContent = 'Kayıtlı kredi kartı yok';
      }
    }

    renderCreditCards();
    renderLoans();
    await loadCreditAnalytics();
  } catch (err) {
    console.error('Error loading credits & loans:', err);
  }
}

function renderCreditCards() {
  const container = document.getElementById('credit-cards-grid');
  if (!container) return;

  if (creditCardsList.length === 0) {
    container.innerHTML = `
      <div class="col-span-3 glass-panel p-6 rounded-2xl text-center border-dashed border-white/20">
        <div class="w-12 h-12 rounded-2xl bg-blue-600/20 text-blue-400 mx-auto flex items-center justify-center mb-3">
          <i data-lucide="credit-card" class="w-6 h-6"></i>
        </div>
        <h4 class="text-sm font-bold text-white">Henüz Kayıtlı Kredi Kartı Yok</h4>
        <p class="text-xs text-gray-400 mt-1 max-w-sm mx-auto">Kartlarınızı ekleyin; hesap kesim ve son ödeme günlerini, limit doluluğunu ve geçmiş ekstreleri takip edelim.</p>
        <button onclick="openModal('modal-credit-card')" class="mt-4 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition inline-flex items-center gap-1.5">
          <i data-lucide="plus" class="w-4 h-4"></i>
          <span>İlk Kredi Kartını Ekle</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = creditCardsList.map(card => {
    const util = card.utilization_rate;
    const utilColor = util > 70 ? 'bg-rose-500' : util > 40 ? 'bg-amber-500' : 'bg-emerald-500';

    // Urgency Badge
    let urgencyBadge = '';
    if (card.urgency_level === 'due_urgent') {
      urgencyBadge = `<span class="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40 text-[10px] font-bold pulse-badge flex items-center gap-1"><i data-lucide="alert-circle" class="w-3 h-3"></i>Son ${card.days_until_due} Gün! (Acil)</span>`;
    } else if (card.urgency_level === 'due_soon') {
      urgencyBadge = `<span class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40 text-[10px] font-bold flex items-center gap-1"><i data-lucide="clock" class="w-3 h-3"></i>${card.days_until_due} Gün Kaldı</span>`;
    } else {
      urgencyBadge = `<span class="px-2 py-0.5 rounded-full bg-white/10 text-gray-300 text-[10px]">${card.days_until_due} gün sonra</span>`;
    }

    // Past unpaid statement warning badge
    const pastUnpaidHtml = (card.unpaid_past_statements_total && card.unpaid_past_statements_total > 0)
      ? `<div class="mt-2 p-2 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-[10px] flex items-center justify-between">
           <span class="flex items-center gap-1"><i data-lucide="alert-triangle" class="w-3 h-3 text-rose-400"></i>Devreden Geçmiş Borç:</span>
           <strong class="font-mono font-bold">${formatTRY(card.unpaid_past_statements_total)}</strong>
         </div>`
      : '';

    return `
      <div class="credit-card-ui p-5 rounded-2xl flex flex-col justify-between shadow-xl" style="--card-glow: ${card.color || 'rgba(99, 102, 241, 0.3)'}">
        <div>
          <div class="flex items-center justify-between mb-3">
            <span class="text-xs font-bold tracking-wider uppercase text-gray-200">${card.bank_name}</span>
            ${urgencyBadge}
          </div>
          <h4 class="text-base font-extrabold text-white">${card.card_name}</h4>
          
          <!-- Exact Timing Dates Row -->
          <div class="grid grid-cols-2 gap-2 my-3 p-2.5 bg-black/40 rounded-xl border border-white/5 text-[11px]">
            <div>
              <span class="text-gray-400 block text-[10px]">⏰ Son Ödeme Günü:</span>
              <strong class="text-amber-400 font-mono">${card.due_date_str}</strong>
              <span class="text-[9px] text-gray-500 block">Her ayın ${card.due_day}. günü</span>
            </div>
            <div class="text-right">
              <span class="text-gray-400 block text-[10px]">🗓️ Hesap Kesim Günü:</span>
              <strong class="text-gray-300 font-mono">${card.cutoff_date_str}</strong>
              <span class="text-[9px] text-gray-500 block">${card.days_until_cutoff} gün sonra kesilecek</span>
            </div>
          </div>

          <!-- Debt Breakdown (Ekstre Borcu vs Güncel Harcama) -->
          <div class="mt-2 flex items-baseline justify-between">
            <div>
              <span class="text-[10px] text-gray-400 block">Ödenecek Ekstre Borcu</span>
              <span class="text-lg font-black text-rose-400 font-mono">${formatTRY(card.statement_debt !== undefined ? card.statement_debt : card.current_debt)}</span>
            </div>
            <div class="text-right">
              <span class="text-[10px] text-gray-400 block">Kullanılabilir Limit</span>
              <span class="text-xs font-bold text-gray-300 font-mono">${formatTRY(card.available_limit)}</span>
            </div>
          </div>

          <!-- Secondary Debts Row (Current Period & Installments) -->
          <div class="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-[10px] text-gray-400">
            <span>Dönem İçi: <strong class="text-gray-200">${formatTRY(card.current_debt || 0)}</strong></span>
            ${card.installment_debt > 0 ? `<span>Kalan Taksit: <strong class="text-amber-300">${formatTRY(card.installment_debt)}</strong></span>` : ''}
          </div>

          ${pastUnpaidHtml}

          <!-- Progress Bar Limit Utilization -->
          <div class="mt-3">
            <div class="flex justify-between text-[10px] text-gray-400 mb-1">
              <span>Limit Doluluğu: %${util}</span>
              <span>Toplam Limit: ${formatTRY(card.total_limit)}</span>
            </div>
            <div class="w-full bg-gray-700/60 rounded-full h-1.5 overflow-hidden">
              <div class="${utilColor} h-1.5 rounded-full" style="width: ${Math.min(100, util)}%"></div>
            </div>
          </div>
        </div>

        <div class="mt-4 pt-3 border-t border-white/10 flex items-center justify-between gap-2 text-xs">
          <div>
            <span class="text-[10px] text-gray-400 block">Asgari</span>
            <strong class="text-white text-xs font-mono">${formatTRY(card.min_payment_amount)}</strong>
          </div>
          <div class="flex items-center gap-1.5">
            <button onclick="openStatementHistoryModal(${card.id})" class="px-2.5 py-1.5 rounded-xl text-[11px] font-semibold bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 transition flex items-center gap-1">
              <i data-lucide="history" class="w-3 h-3"></i>
              <span>Geçmiş Ekstreler</span>
            </button>
            <button onclick="openCardUpdateModal(${card.id})" class="px-2.5 py-1.5 rounded-xl text-[11px] font-semibold bg-white/10 hover:bg-white/20 text-white transition flex items-center gap-1">
              <i data-lucide="edit-3" class="w-3 h-3"></i>
              <span>Düzenle</span>
            </button>
            <button onclick="promptDeleteCreditCard(${card.id}, '${card.card_name}')" title="Kartı Sil" class="p-1.5 rounded-xl text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 transition">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function renderLoans() {
  const container = document.getElementById('loans-grid');
  if (!container) return;

  if (loansList.length === 0) {
    container.innerHTML = `
      <div class="col-span-2 glass-panel p-6 rounded-2xl text-center border-dashed border-white/20">
        <h4 class="text-xs font-bold text-gray-300">Aktif Kredi Taksiti Bulunmuyor</h4>
        <p class="text-[11px] text-gray-500 mt-1">İhtiyaç veya taşıt krediniz varsa ekleyerek bitiş tarihini takip edebilirsiniz.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = loansList.map(loan => {
    const progressPct = Math.round((loan.paid_installments / loan.total_installments) * 100);

    return `
      <div class="glass-panel p-5 rounded-2xl flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <div class="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center">
                <i data-lucide="landmark" class="w-4 h-4"></i>
              </div>
              <div>
                <h4 class="text-xs font-bold text-white">${loan.bank_name}</h4>
                <p class="text-[11px] text-gray-400">${loan.loan_title}</p>
              </div>
            </div>
            <span class="text-xs font-bold text-amber-400 font-mono">${formatTRY(loan.monthly_installment)} / ay</span>
          </div>

          <div class="grid grid-cols-2 gap-2 my-3 p-3 bg-white/5 rounded-xl text-xs">
            <div>
              <span class="text-[10px] text-gray-400 block">Kalan Anapara Borcu</span>
              <span class="font-extrabold text-white font-mono text-sm">${formatTRY(loan.remaining_principal)}</span>
            </div>
            <div class="text-right">
              <span class="text-[10px] text-gray-400 block">Bitiş Tahmini</span>
              <span class="font-bold text-indigo-400 text-xs">${loan.end_date_estimate}</span>
            </div>
          </div>

          <div class="space-y-1">
            <div class="flex justify-between text-[11px] text-gray-400">
              <span>Taksit İlerlemesi: <strong>${loan.paid_installments} / ${loan.total_installments}</strong></span>
              <span>Kalan: <strong>${loan.remaining_installments} ay</strong></span>
            </div>
            <div class="w-full bg-gray-700/50 rounded-full h-2 overflow-hidden">
              <div class="bg-gradient-to-r from-amber-500 to-emerald-500 h-2 rounded-full" style="width: ${progressPct}%"></div>
            </div>
          </div>
        </div>

        <div class="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-[11px] text-gray-400">
          <div>
            <span>Her ayın <strong>${loan.due_day}</strong>. günü kesilir</span>
            <span class="text-indigo-400 font-semibold ml-2">${loan.due_date_str} (${loan.days_until_due} gün kaldı)</span>
          </div>
          <button onclick="promptDeleteLoan(${loan.id}, '${loan.loan_title}')" title="Krediyi Sil" class="p-1.5 rounded-xl text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 transition">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

async function promptPayCard(cardId, cardName, currentDebt) {
  const newDebtStr = prompt(`"${cardName}" için yeni güncel borç tutarını girin (Ödeme yaptıysanız 0 yazabilirsiniz):`, currentDebt);
  if (newDebtStr !== null) {
    const newDebt = parseFloat(newDebtStr);
    if (!isNaN(newDebt)) {
      const res = await authFetch(`${API_BASE}/credits/cards/${cardId}/debt?new_debt=${newDebt}&statement_debt=${newDebt}`, {
        method: 'PUT'
      });
      if (res.ok) {
        showToast('Kart borcu güncellendi', '💳');
        await refreshAllData();
      }
    }
  }
}

// ==========================================
// CREDIT CARD ANALYTICS, LIMITS & STATEMENTS
// ==========================================
async function loadCreditAnalytics() {
  try {
    const res = await authFetch(`${API_BASE}/credits/cards/analytics`);
    if (!res.ok) return;
    const a = await res.json();
    const elLimits = document.getElementById('ca-total-limits');
    const elStmt = document.getElementById('ca-total-statements');
    const elInst = document.getElementById('ca-total-installments');
    const elAvail = document.getElementById('ca-total-available');
    const elUtil = document.getElementById('ca-utilization');
    if (elLimits) elLimits.textContent = formatTRY(a.total_limits_all_cards);
    if (elStmt) elStmt.textContent = formatTRY(a.total_statement_debt_all);
    if (elInst) elInst.textContent = formatTRY(a.total_installment_debt_all);
    if (elAvail) elAvail.textContent = formatTRY(a.total_available_limit_all);
    if (elUtil) {
      elUtil.textContent = `%${a.overall_utilization_rate}`;
      elUtil.className = `font-extrabold font-mono text-sm ${a.overall_utilization_rate > 70 ? 'text-rose-400' : a.overall_utilization_rate > 40 ? 'text-amber-400' : 'text-emerald-400'}`;
    }
  } catch (err) {
    console.error('Error loading credit analytics:', err);
  }
}

function openCardUpdateModal(cardId) {
  const card = creditCardsList.find(c => c.id === cardId);
  if (!card) return;

  document.getElementById('update-card-id').value = card.id;
  document.getElementById('update-card-title').textContent = card.card_name;
  document.getElementById('update-card-bank').textContent = `${card.bank_name} (Kesim: ${card.cutoff_day}. gün, Son Ödeme: ${card.due_day}. gün)`;
  document.getElementById('update-card-limit').value = card.total_limit;
  document.getElementById('update-card-stmt-debt').value = card.statement_debt || 0;
  document.getElementById('update-card-curr-debt').value = card.current_debt || 0;
  document.getElementById('update-card-inst-debt').value = card.installment_debt || 0;
  document.getElementById('update-card-interest').value = card.interest_rate || 4.25;

  openModal('modal-card-update');
}

async function handleCardLimitDebtSubmit(e) {
  e.preventDefault();
  const cardId = parseInt(document.getElementById('update-card-id').value);
  if (!cardId) return;

  const payload = {
    total_limit: parseFloat(document.getElementById('update-card-limit').value),
    statement_debt: parseFloat(document.getElementById('update-card-stmt-debt').value) || 0,
    current_debt: parseFloat(document.getElementById('update-card-curr-debt').value) || 0,
    installment_debt: parseFloat(document.getElementById('update-card-inst-debt').value) || 0,
    interest_rate: parseFloat(document.getElementById('update-card-interest').value) || 4.25
  };

  try {
    const res = await authFetch(`${API_BASE}/credits/cards/${cardId}/limits-and-debts`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      closeModal('modal-card-update');
      showToast('Kart limitleri ve borçları başarıyla güncellendi!', '💳');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Güncelleme başarısız', '⚠️');
    }
  } catch (err) {
    console.error('Card update error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function openStatementHistoryModal(cardId) {
  const card = creditCardsList.find(c => c.id === cardId);
  if (!card) return;

  document.getElementById('add-stmt-card-id').value = card.id;
  document.getElementById('stmt-modal-card-title').textContent = `${card.card_name} - Geçmiş Ekstreler`;
  document.getElementById('stmt-modal-card-bank').textContent = `${card.bank_name} • Limit: ${formatTRY(card.total_limit)} • Kesim: ${card.cutoff_day}. gün • Son Ödeme: ${card.due_day}. gün`;

  // Reset form
  const form = document.getElementById('form-add-statement');
  if (form) {
    form.classList.add('hidden');
    form.reset();
  }

  // Pre-fill default dates
  const today = new Date();
  const monthNames = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const prevMonthIndex = today.getMonth() === 0 ? 11 : today.getMonth() - 1;
  const prevYear = today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();
  document.getElementById('add-stmt-period').value = `${monthNames[prevMonthIndex]} ${prevYear}`;
  
  // Set default due date
  const dueDayFormatted = String(card.due_day).padStart(2, '0');
  const monthFormatted = String(today.getMonth() + 1).padStart(2, '0');
  document.getElementById('add-stmt-due-date').value = `${today.getFullYear()}-${monthFormatted}-${dueDayFormatted}`;

  openModal('modal-statement-history');
  await loadAndRenderStatements(cardId);
}

async function loadAndRenderStatements(cardId) {
  const tbody = document.getElementById('statements-table-tbody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="7" class="py-4 text-center text-gray-400">Yükleniyor...</td></tr>`;

  try {
    const res = await authFetch(`${API_BASE}/credits/cards/${cardId}/statements`);
    const statements = await res.json();
    renderStatementsTable(statements, cardId);
  } catch (err) {
    console.error('Error loading statements:', err);
    tbody.innerHTML = `<tr><td colspan="7" class="py-4 text-center text-rose-400">Ekstreler yüklenemedi.</td></tr>`;
  }
}

function renderStatementsTable(statements, cardId) {
  const tbody = document.getElementById('statements-table-tbody');
  if (!tbody) return;

  if (!statements || statements.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-gray-500">Bu karta ait henüz ekstre kaydı bulunmuyor. Üst kısımdan geçmiş ekstrelerinizi ekleyebilirsiniz.</td></tr>`;
    return;
  }

  tbody.innerHTML = statements.map(s => {
    let statusBadge = '';
    if (s.status === 'paid') {
      statusBadge = `<span class="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold">Ödendi</span>`;
    } else if (s.status === 'partially_paid') {
      statusBadge = `<span class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] font-bold">Kısmi</span>`;
    } else {
      statusBadge = `<span class="px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[10px] font-bold">Ödenmedi</span>`;
    }

    const remaining = s.remaining_debt !== undefined && s.remaining_debt !== null ? s.remaining_debt : Math.max(0, s.statement_amount - (s.paid_amount || 0));
    const remColor = remaining > 0 ? 'text-rose-400 font-bold' : 'text-gray-400';
    const interestStr = s.estimated_interest > 0 ? `+${formatTRY(s.estimated_interest)}` : '-';

    return `
      <tr class="hover:bg-white/5 transition">
        <td class="py-3">
          <strong class="font-bold text-white block">${s.period}</strong>
          <span class="text-[10px] text-gray-400 font-mono">Son Ödeme: ${s.due_date || '-'}</span>
        </td>
        <td class="py-3 text-right font-mono font-bold text-gray-200">${formatTRY(s.statement_amount)}</td>
        <td class="py-3 text-right font-mono text-emerald-400">${formatTRY(s.paid_amount || 0)}</td>
        <td class="py-3 text-right font-mono ${remColor}">${formatTRY(remaining)}</td>
        <td class="py-3 text-center">${statusBadge}</td>
        <td class="py-3 text-right font-mono text-xs text-amber-400">${interestStr}</td>
        <td class="py-3 text-center">
          <button onclick="deleteCardStatement(${s.id}, ${cardId})" class="p-1 text-gray-400 hover:text-rose-400 transition" title="Ekstreyi Sil">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function toggleAddStatementForm() {
  const form = document.getElementById('form-add-statement');
  if (form) {
    form.classList.toggle('hidden');
    if (window.lucide) lucide.createIcons();
  }
}

async function handleAddStatementSubmit(e) {
  e.preventDefault();
  const cardId = parseInt(document.getElementById('add-stmt-card-id').value);
  if (!cardId) return;

  const payload = {
    credit_card_id: cardId,
    period: document.getElementById('add-stmt-period').value.trim(),
    due_date: document.getElementById('add-stmt-due-date').value,
    statement_amount: parseFloat(document.getElementById('add-stmt-amount').value),
    paid_amount: parseFloat(document.getElementById('add-stmt-paid').value) || 0.0,
    min_payment_amount: parseFloat(document.getElementById('add-stmt-min').value) || null
  };

  try {
    const res = await authFetch(`${API_BASE}/credits/cards/${cardId}/statements`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast('Ekstre kaydı başarıyla eklendi!', '📄');
      document.getElementById('form-add-statement').classList.add('hidden');
      document.getElementById('add-stmt-amount').value = '';
      document.getElementById('add-stmt-paid').value = '';
      document.getElementById('add-stmt-min').value = '';

      await loadAndRenderStatements(cardId);
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Ekstre eklenemedi', '⚠️');
    }
  } catch (err) {
    console.error('Error saving statement:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function deleteCardStatement(statementId, cardId) {
  if (!confirm('Bu ekstre kaydını silmek istediğinize emin misiniz?')) return;

  try {
    const res = await authFetch(`${API_BASE}/credits/statements/${statementId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast('Ekstre kaydı silindi', '🗑️');
      await loadAndRenderStatements(cardId);
      await refreshAllData();
    } else {
      showToast('Ekstre silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Delete error:', err);
    showToast('Silme işlemi başarısız', '⚠️');
  }
}

// ==========================================
// 3. CASH FLOW & SIMULATION (MODULE 4)
// ==========================================
async function loadSimulation(customSpend = null, extraExpense = 0.0) {
  try {
    let url = `${API_BASE}/simulation?`;
    if (customSpend !== null) url += `custom_daily_spend=${customSpend}&`;
    if (extraExpense > 0) url += `extra_expense=${extraExpense}&`;

    const res = await authFetch(url);
    simulationData = await res.json();

    updateSimulationUI();
    renderCashFlowChart();
  } catch (err) {
    console.error('Error loading simulation:', err);
  }
}

function updateSimulationUI() {
  if (!simulationData) return;

  const {
    status, status_headline, status_summary,
    projected_end_of_month_balance, critical_dip_day, critical_dip_amount,
    remaining_days_in_month, recommended_max_daily_spend,
    total_upcoming_fixed_bills, total_upcoming_credit_payments,
    total_upcoming_loan_payments, alerts
  } = simulationData;

  const teaserBanner = document.getElementById('overview-sim-banner');
  const teaserTag = document.getElementById('sim-banner-status-tag');
  const teaserHead = document.getElementById('sim-banner-headline');
  const teaserDesc = document.getElementById('sim-banner-desc');
  const teaserIcon = document.getElementById('sim-banner-icon-box');

  const heroCard = document.getElementById('sim-hero-card');
  const heroBadge = document.getElementById('sim-hero-badge');
  const heroStatusText = document.getElementById('sim-hero-status-text');
  const heroHeadline = document.getElementById('sim-hero-headline');
  const heroSummary = document.getElementById('sim-hero-summary');
  const heroFinalBal = document.getElementById('sim-hero-final-balance');
  const heroDipNote = document.getElementById('sim-hero-dip-note');

  heroFinalBal.textContent = formatTRY(projected_end_of_month_balance);
  heroFinalBal.className = `text-3xl font-black font-mono block mt-1 ${projected_end_of_month_balance >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;

  if (critical_dip_amount !== null && critical_dip_day) {
    heroDipNote.textContent = `En düşük dip: ${critical_dip_day} (${formatTRY(critical_dip_amount)})`;
  } else {
    heroDipNote.textContent = 'Henüz kritik risk yok';
  }

  document.getElementById('sim-stat-days').textContent = `${remaining_days_in_month} Gün`;
  document.getElementById('sim-stat-debts').textContent = formatTRY(total_upcoming_credit_payments + total_upcoming_loan_payments);
  document.getElementById('sim-stat-bills').textContent = formatTRY(total_upcoming_fixed_bills);
  document.getElementById('sim-stat-rec-spend').textContent = `${formatTRY(recommended_max_daily_spend)} / gün`;
  const elHeroDaily = document.getElementById('hero-daily-budget');
  if (elHeroDaily && recommended_max_daily_spend !== undefined) {
    elHeroDaily.textContent = `${formatTRY(recommended_max_daily_spend)} / gün`;
  }

  if (status === 'SURPLUS_SAFE') {
    if (teaserBanner) {
      teaserBanner.className = 'glass-panel p-4 lg:p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-l-4 border-emerald-500 glow-emerald';
      teaserTag.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
      teaserTag.textContent = 'GÜVENLİ BÖLGE';
      teaserIcon.className = 'w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0';
    }
    heroCard.className = 'glass-panel p-6 lg:p-8 rounded-3xl border-2 border-emerald-500/40 glow-emerald transition-all';
    heroBadge.className = 'inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    heroStatusText.textContent = 'GÜVENLİ BÖLGE (ARTIDASINIZ)';
  } else if (status === 'LIQUIDITY_DANGER') {
    if (teaserBanner) {
      teaserBanner.className = 'glass-panel p-4 lg:p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-l-4 border-amber-500 glow-amber';
      teaserTag.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30';
      teaserTag.textContent = 'LİKİDİTE DARBOĞAZI';
      teaserIcon.className = 'w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center shrink-0';
    }
    heroCard.className = 'glass-panel p-6 lg:p-8 rounded-3xl border-2 border-amber-500/40 glow-amber transition-all';
    heroBadge.className = 'inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30';
    heroStatusText.textContent = 'DİKKAT: ARA DÖNEM LİKİDİTE RİSKİ';
  } else {
    if (teaserBanner) {
      teaserBanner.className = 'glass-panel p-4 lg:p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-l-4 border-rose-500 glow-rose';
      teaserTag.className = 'text-[10px] px-2 py-0.5 rounded-full font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30';
      teaserTag.textContent = 'BÜTÇE AÇIĞI RİSKİ';
      teaserIcon.className = 'w-10 h-10 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center shrink-0';
    }
    heroCard.className = 'glass-panel p-6 lg:p-8 rounded-3xl border-2 border-rose-500/40 glow-rose transition-all';
    heroBadge.className = 'inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30';
    heroStatusText.textContent = 'ALARM: BÜTÇE AÇIĞI GÖRÜNÜYOR';
  }

  if (teaserHead) teaserHead.textContent = status_headline;
  if (teaserDesc) teaserDesc.textContent = status_summary;
  heroHeadline.textContent = status_headline;
  heroSummary.textContent = status_summary;

  renderDangerAlerts(alerts);
  renderUpcomingPayments(simulationData.upcoming_payments || []);
}

let currentUpcomingFilter = 'all';
let cachedUpcomingPayments = [];

function filterUpcomingPayments(filterType) {
  currentUpcomingFilter = filterType;
  const btnIds = ['all', 'credit_card', 'loan', 'recurring_expense', 'recurring_income'];
  btnIds.forEach(b => {
    const el = document.getElementById(`btn-up-filter-${b}`);
    if (el) {
      if (b === filterType) {
        el.className = 'px-3 py-1.5 rounded-lg font-semibold bg-indigo-600 text-white transition whitespace-nowrap shadow-sm';
      } else {
        el.className = 'px-3 py-1.5 rounded-lg text-gray-400 hover:text-white transition whitespace-nowrap';
      }
    }
  });

  const filtered = filterType === 'all' 
    ? cachedUpcomingPayments 
    : cachedUpcomingPayments.filter(p => p.payment_type === filterType);

  renderUpcomingPaymentsList(filtered);
}

function renderUpcomingPayments(payments) {
  cachedUpcomingPayments = payments || [];

  // Update summary stats
  const totalCards = cachedUpcomingPayments.filter(p => p.payment_type === 'credit_card').reduce((s, p) => s + p.amount, 0);
  const totalLoans = cachedUpcomingPayments.filter(p => p.payment_type === 'loan').reduce((s, p) => s + p.amount, 0);
  const totalBills = cachedUpcomingPayments.filter(p => p.payment_type === 'recurring_expense').reduce((s, p) => s + p.amount, 0);
  const totalInflows = cachedUpcomingPayments.filter(p => p.payment_type === 'recurring_income').reduce((s, p) => s + p.amount, 0);

  const elCards = document.getElementById('up-stat-cards');
  const elLoans = document.getElementById('up-stat-loans');
  const elBills = document.getElementById('up-stat-bills');
  const elInflows = document.getElementById('up-stat-inflows');

  if (elCards) elCards.textContent = formatTRY(totalCards);
  if (elLoans) elLoans.textContent = formatTRY(totalLoans);
  if (elBills) elBills.textContent = formatTRY(totalBills);
  if (elInflows) elInflows.textContent = formatTRY(totalInflows);

  filterUpcomingPayments(currentUpcomingFilter);
}

function renderUpcomingPaymentsList(payments) {
  const container = document.getElementById('upcoming-payments-container');
  if (!container) return;

  if (!payments || payments.length === 0) {
    container.innerHTML = `
      <div class="p-6 rounded-2xl bg-white/5 border border-white/5 text-center text-gray-400 text-xs">
        Bu filtreye ait bekleyen bir ödeme veya gelir kaydı bulunmuyor.
      </div>
    `;
    return;
  }

  container.innerHTML = payments.map(p => {
    const isInc = p.payment_type === 'recurring_income';
    let typeIcon = 'receipt';
    let iconBg = 'bg-blue-500/20 text-blue-400';
    let borderTheme = 'border-white/10';

    if (p.payment_type === 'credit_card') {
      typeIcon = 'credit-card';
      iconBg = 'bg-purple-500/20 text-purple-400';
    } else if (p.payment_type === 'loan') {
      typeIcon = 'landmark';
      iconBg = 'bg-amber-500/20 text-amber-400';
    } else if (isInc) {
      typeIcon = 'trending-up';
      iconBg = 'bg-emerald-500/20 text-emerald-400';
    }

    let statusBadge = '';
    if (p.coverage_status === 'sufficient') {
      statusBadge = `<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">🟢 Kasa Karşılıyor</span>`;
    } else if (p.coverage_status === 'warning') {
      statusBadge = `<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">🟡 Kritik Bakiye</span>`;
      borderTheme = 'border-amber-500/30';
    } else {
      statusBadge = `<span class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">🔴 Açık: ${formatTRY(p.coverage_deficit)}</span>`;
      borderTheme = 'border-rose-500/40 glow-rose';
    }

    const daysBadge = p.days_left === 0 
      ? `<span class="px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 font-bold text-[10px] border border-rose-500/30">BUGÜN</span>`
      : `<span class="px-2 py-0.5 rounded-md bg-white/10 text-gray-300 font-mono text-[10px]">${p.days_left} gün kaldı</span>`;

    return `
      <div class="glass-panel p-4 rounded-2xl border ${borderTheme} flex flex-col md:flex-row md:items-center justify-between gap-4 transition hover:bg-white/5">
        <div class="flex items-start gap-3.5">
          <div class="w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center shrink-0">
            <i data-lucide="${typeIcon}" class="w-5 h-5"></i>
          </div>
          <div class="space-y-1">
            <div class="flex items-center gap-2 flex-wrap">
              <h4 class="text-sm font-bold text-white">${p.title}</h4>
              <span class="text-[10px] text-gray-400 bg-white/5 px-2 py-0.5 rounded-md">${p.payment_type_label}</span>
              ${daysBadge}
            </div>
            <div class="text-xs text-gray-400 flex items-center gap-2">
              <span>📅 Vade: <strong class="text-gray-200">${p.due_date_str}</strong></span>
              <span>•</span>
              <span>Kurum: <strong class="text-gray-200">${p.institution}</strong></span>
            </div>
            ${p.advice_note ? `
              <div class="text-[11px] text-gray-300 bg-black/20 p-2 rounded-lg border border-white/5 flex items-start gap-1.5 mt-1.5 max-w-xl">
                <i data-lucide="sparkles" class="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5"></i>
                <span>${p.advice_note}</span>
              </div>
            ` : ''}
          </div>
        </div>

        <div class="flex items-center justify-between md:flex-col md:items-end gap-2 shrink-0 pt-3 md:pt-0 border-t md:border-t-0 border-white/5">
          <div class="text-left md:text-right">
            <span class="text-[10px] text-gray-400 block">${isInc ? 'Beklenen Gelir' : 'Ödenecek Tutar'}</span>
            <span class="text-base font-extrabold font-mono ${isInc ? 'text-emerald-400' : 'text-white'}">
              ${isInc ? '+' : '-'}${formatTRY(p.amount)}
            </span>
            ${p.min_amount ? `
              <span class="text-[10px] text-amber-400 block font-mono">Asgari: ${formatTRY(p.min_amount)}</span>
            ` : ''}
          </div>

          <div class="text-right">
            ${statusBadge}
            <span class="text-[10px] text-gray-400 block mt-1 font-mono">
              Ödeme Sonrası Kasa: <strong class="${p.balance_after_payment >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${formatTRY(p.balance_after_payment)}</strong>
            </span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}


function renderDangerAlerts(alerts) {
  const container = document.getElementById('sim-alerts-container');
  if (!container) return;

  if (!alerts || alerts.length === 0) {
    container.innerHTML = `
      <div class="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-3">
        <i data-lucide="check-circle" class="w-5 h-5 shrink-0"></i>
        <span>Kritik bir likidite darboğazı veya bütçe açığı tespit edilmedi. Nakit akışınız dengede!</span>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = alerts.map(a => {
    const isDanger = a.severity === 'danger';
    const borderCol = isDanger ? 'border-rose-500/40 bg-rose-950/20 text-rose-200' : 'border-amber-500/40 bg-amber-950/20 text-amber-200';
    const iconName = isDanger ? 'alert-octagon' : 'alert-triangle';

    return `
      <div class="p-4 rounded-xl border ${borderCol} flex items-start justify-between gap-3 text-xs">
        <div class="flex items-start gap-3">
          <i data-lucide="${iconName}" class="w-5 h-5 shrink-0 mt-0.5"></i>
          <div>
            <div class="flex items-center gap-2">
              <strong class="font-bold text-white">${a.title}</strong>
              <span class="text-[10px] bg-white/10 px-2 py-0.5 rounded-md font-mono">${a.date}</span>
            </div>
            <p class="mt-1 text-gray-300 text-[11px] leading-relaxed">${a.message}</p>
          </div>
        </div>
        <div class="text-right shrink-0">
          <span class="text-[10px] text-gray-400 block">Kalan Bakiye</span>
          <span class="font-bold font-mono text-sm ${a.projected_balance >= 0 ? 'text-white' : 'text-rose-400'}">${formatTRY(a.projected_balance)}</span>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function renderCashFlowChart() {
  const ctx = document.getElementById('cashFlowChart');
  if (!ctx || !simulationData) return;

  const points = simulationData.projection_curve;
  const labels = points.map(p => {
    const parts = p.date.split('-');
    return `${parts[2]}.${parts[1]}`;
  });
  const dataValues = points.map(p => p.projected_balance);

  if (cashFlowChartInstance) {
    cashFlowChartInstance.destroy();
  }

  const chartContext = ctx.getContext('2d');
  const gradient = chartContext.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.4)');
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

  const chartDatasets = [
    {
      label: 'Tahmini Kasa Bakiyesi (₺)',
      data: dataValues,
      borderColor: '#10b981',
      borderWidth: 2.5,
      pointBackgroundColor: points.map(p => p.is_critical ? '#ef4444' : '#10b981'),
      pointRadius: points.map(p => p.is_critical ? 5 : 2),
      pointHoverRadius: 6,
      backgroundColor: gradient,
      fill: true,
      tension: 0.35
    },
    {
      label: 'Sıfır Eşiği (0 ₺)',
      data: Array(labels.length).fill(0),
      borderColor: 'rgba(244, 63, 94, 0.6)',
      borderWidth: 1.5,
      borderDash: [5, 5],
      pointRadius: 0,
      fill: false
    }
  ];

  if (whatIfSimulationData && whatIfSimulationData.timeline_whatif && whatIfSimulationData.timeline_whatif.length > 0) {
    chartDatasets.push({
      label: `What-If: ${whatIfSimulationData.scenario_title || 'Senaryo'}`,
      data: whatIfSimulationData.timeline_whatif.map(p => p.projected_balance),
      borderColor: '#818cf8',
      borderWidth: 2.5,
      borderDash: [4, 4],
      pointBackgroundColor: whatIfSimulationData.timeline_whatif.map(p => p.is_critical ? '#ef4444' : '#818cf8'),
      pointRadius: whatIfSimulationData.timeline_whatif.map(p => p.is_critical ? 5 : 2),
      pointHoverRadius: 6,
      fill: false,
      tension: 0.35
    });
  }

  cashFlowChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: chartDatasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(17, 24, 39, 0.95)',
          titleFont: { size: 12, weight: 'bold' },
          bodyFont: { size: 11 },
          padding: 10,
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
          callbacks: {
            label: function(context) {
              const idx = context.dataIndex;
              const pt = points[idx];
              const lines = [`Kasa: ${formatTRY(pt.projected_balance)}`];
              if (pt.events && pt.events.length > 0) {
                lines.push(...pt.events);
              }
              return lines;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#9ca3af', font: { size: 10 } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#9ca3af',
            font: { size: 10 },
            callback: value => `${value.toLocaleString('tr-TR')} ₺`
          }
        }
      }
    }
  });
}

function onSimulationSliderChange(val) {
  document.getElementById('sim-slider-label').textContent = `${parseInt(val).toLocaleString('tr-TR')} ₺ / gün`;
  loadSimulation(parseFloat(val));
}

function applyOneTimeSimExpense() {
  const input = document.getElementById('sim-extra-expense-input');
  const val = parseFloat(input.value) || 0;
  const sliderVal = parseFloat(document.getElementById('sim-daily-slider').value) || 0;
  loadSimulation(sliderVal, val);
  showToast(`Simülasyona ${formatTRY(val)} harcama dahil edildi!`, '🔮');
}

function resetSimulationControls() {
  document.getElementById('sim-daily-slider').value = 0;
  document.getElementById('sim-slider-label').textContent = '0 ₺ / gün';
  document.getElementById('sim-extra-expense-input').value = '';
  loadSimulation(null, 0);
  showToast('Simülasyon sıfırlandı.', '🔄');
}

// ==========================================
// 4. TRANSACTIONS & CATEGORY BREAKDOWN (MODULE 2)
// ==========================================
async function loadCategories() {
  try {
    const res = await fetch(`${API_BASE}/transactions/categories`);
    categoriesList = await res.json();

    const manualCat = document.getElementById('manual-category');
    const nlpCat = document.getElementById('nlp-confirm-category');
    const recCat = document.getElementById('rec-category');

    const options = categoriesList.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    if (manualCat) manualCat.innerHTML = options;
    if (nlpCat) nlpCat.innerHTML = options;
    if (recCat) recCat.innerHTML = options;
  } catch (err) {
    console.error('Error loading categories:', err);
  }
}

async function loadTransactions() {
  try {
    const filterType = document.getElementById('trans-filter-type')?.value || '';
    let url = `${API_BASE}/transactions?limit=50`;
    if (filterType) url += `&trans_type=${filterType}`;

    const res = await authFetch(url);
    const transactions = await res.json();

    renderOverviewTransactions(transactions.slice(0, 7));
    renderFullTransactions(transactions);
  } catch (err) {
    console.error('Error loading transactions:', err);
  }
}

function renderOverviewTransactions(transactions) {
  const tbody = document.getElementById('overview-transactions-tbody');
  if (!tbody) return;

  if (transactions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-gray-500">Henüz kayıtlı harcama veya gelir yok.</td></tr>`;
    return;
  }

  tbody.innerHTML = transactions.map(t => {
    const isExp = t.type === 'expense';
    const sign = isExp ? '-' : '+';
    const amtColor = isExp ? 'text-gray-200' : 'text-emerald-400 font-bold';
    const methodStr = t.card_name || t.account_name || (t.payment_method === 'cash' ? 'Nakit' : 'Banka');

    return `
      <tr class="hover:bg-white/5 transition">
        <td class="py-2.5 text-gray-400 font-mono text-[11px]">${t.date}</td>
        <td class="py-2.5">
          <span class="font-medium text-white block">${t.description}</span>
          <span class="text-[10px] text-gray-500">${t.category}</span>
        </td>
        <td class="py-2.5 text-gray-400 text-[11px]">${methodStr}</td>
        <td class="py-2.5 text-right font-mono font-bold ${amtColor}">${sign}${formatTRY(t.amount)}</td>
      </tr>
    `;
  }).join('');
}

function renderFullTransactions(transactions) {
  const tbody = document.getElementById('transactions-full-tbody');
  if (!tbody) return;

  if (transactions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="py-8 text-center text-gray-500">Henüz kayıtlı işlem bulunmuyor. Üst kısımdan ilk harcamanızı ekleyebilirsiniz.</td></tr>`;
    return;
  }

  tbody.innerHTML = transactions.map(t => {
    const isExp = t.type === 'expense';
    const sign = isExp ? '-' : '+';
    const amtColor = isExp ? 'text-gray-200' : 'text-emerald-400 font-bold';
    const methodStr = t.card_name || t.account_name || (t.payment_method === 'cash' ? 'Nakit' : 'Hesap');
    const nlpBadge = t.is_nlp_generated === 1
      ? `<span class="ml-1.5 text-[9px] bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 px-1 py-0.5 rounded">AI Girişi</span>`
      : '';

    return `
      <tr class="hover:bg-white/5 transition">
        <td class="py-3 text-gray-400 font-mono text-xs">${t.date}</td>
        <td class="py-3 font-medium text-white">${t.description} ${nlpBadge}</td>
        <td class="py-3 text-gray-400 text-xs">
          <span class="bg-white/5 border border-white/5 px-2 py-0.5 rounded-md text-[11px]">${t.category}</span>
        </td>
        <td class="py-3 text-gray-400 text-xs">${methodStr}</td>
        <td class="py-3 text-right font-mono font-bold ${amtColor}">${sign}${formatTRY(t.amount)}</td>
        <td class="py-3 text-center">
          <button onclick="promptDeleteTransaction(${t.id}, '${t.description}')" title="İşlemi Sil" class="p-1 rounded-lg text-gray-500 hover:text-rose-400 hover:bg-rose-500/10 transition">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

async function loadMonthlyComparison() {
  try {
    const res = await authFetch(`${API_BASE}/transactions/monthly-comparison`);
    const data = await res.json();

    renderComparisonTable(data);
    renderCategoryDoughnut(data.categories);
  } catch (err) {
    console.error('Error loading monthly comparison:', err);
  }
}

function renderComparisonTable(data) {
  const headline = document.getElementById('comparison-headline');
  const tbody = document.getElementById('category-comparison-tbody');
  if (!tbody) return;

  if (headline) {
    headline.textContent = `Bu Ay: ${formatTRY(data.this_month_total)} | Geçen Ay: ${formatTRY(data.last_month_total)}`;
  }

  if (!data.categories || data.categories.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-gray-500">Bu ay için henüz harcama verisi girilmemiş.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.categories.map(c => {
    const pct = c.percent_change;
    const isIncrease = pct > 0;
    const pctBadge = isIncrease
      ? `<span class="text-rose-400 font-bold font-mono">+%${pct} ↑</span>`
      : pct < 0
      ? `<span class="text-emerald-400 font-bold font-mono">-%${Math.abs(pct)} ↓</span>`
      : `<span class="text-gray-400 font-mono">%0</span>`;

    return `
      <tr class="hover:bg-white/5 transition">
        <td class="py-3 font-medium text-white">${c.category}</td>
        <td class="py-3 text-right font-mono font-bold text-gray-200">${formatTRY(c.this_month)}</td>
        <td class="py-3 text-right font-mono text-gray-400">${formatTRY(c.last_month)}</td>
        <td class="py-3 text-right">${pctBadge}</td>
        <td class="py-3 text-right font-mono text-xs ${c.diff > 0 ? 'text-rose-400' : 'text-emerald-400'}">${c.diff > 0 ? '+' : ''}${formatTRY(c.diff)}</td>
      </tr>
    `;
  }).join('');
}

function renderCategoryDoughnut(categories) {
  const ctx = document.getElementById('categoryChart');
  const legendList = document.getElementById('category-legend-list');
  if (!ctx || !categories) return;

  const filtered = categories.filter(c => c.this_month > 0);
  const labels = filtered.map(c => c.category);
  const values = filtered.map(c => c.this_month);

  const colors = [
    '#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#06b6d4',
    '#8b5cf6', '#ec4899', '#3b82f6', '#14b8a6', '#84cc16'
  ];

  if (categoryChartInstance) {
    categoryChartInstance.destroy();
  }

  categoryChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.length > 0 ? labels : ['Harcama Yok'],
      datasets: [{
        data: values.length > 0 ? values : [1],
        backgroundColor: values.length > 0 ? colors.slice(0, labels.length) : ['rgba(255,255,255,0.05)'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: { display: false }
      }
    }
  });

  if (legendList) {
    if (filtered.length === 0) {
      legendList.innerHTML = `<p class="text-[11px] text-gray-500 text-center py-2">Henüz harcama kaydı yok</p>`;
    } else {
      legendList.innerHTML = filtered.map((c, i) => `
        <div class="flex items-center justify-between text-xs py-0.5">
          <div class="flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${colors[i % colors.length]}"></span>
            <span class="text-gray-300 text-[11px] truncate max-w-[130px]">${c.category}</span>
          </div>
          <span class="font-mono text-white text-[11px] font-semibold">${formatTRY(c.this_month)}</span>
        </div>
      `).join('');
    }
  }
}

async function loadRecurringItems() {
  try {
    const res = await authFetch(`${API_BASE}/transactions/recurring`);
    const items = await res.json();
    const container = document.getElementById('recurring-items-grid');
    if (!container) return;

    if (items.length === 0) {
      container.innerHTML = `<p class="text-xs text-gray-500 col-span-3">Henüz düzenli ödeme (Maaş/Kira/Fatura) kuralı eklenmemiş.</p>`;
      return;
    }

    container.innerHTML = items.map(item => {
      const isIncome = item.type === 'income';
      return `
        <div class="p-3.5 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between">
          <div>
            <div class="flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full ${isIncome ? 'bg-emerald-400' : 'bg-rose-400'}"></span>
              <h5 class="text-xs font-bold text-white">${item.title}</h5>
            </div>
            <span class="text-[10px] text-gray-400 block mt-0.5">Her ayın ${item.day_of_month}. günü (${item.category})</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-extrabold font-mono ${isIncome ? 'text-emerald-400' : 'text-gray-200'}">
              ${isIncome ? '+' : '-'}${formatTRY(item.amount)}
            </span>
            <button onclick="promptDeleteRecurring(${item.id}, '${item.title}')" title="Kuralı Sil" class="p-1 rounded-lg text-gray-500 hover:text-rose-400 hover:bg-rose-500/10 transition">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error('Error loading recurring:', err);
  }
}

// ==========================================
// 5. NLP SMART NATURAL LANGUAGE (MODULE 2)
// ==========================================
function setNLPInput(text) {
  const input = document.getElementById('nlp-input');
  if (input) {
    input.value = text;
    handleNLPSubmit();
  }
}

async function handleNLPSubmit() {
  const input = document.getElementById('nlp-input');
  const text = input.value.trim();
  if (!text) return;

  const btn = document.getElementById('nlp-submit-btn');
  btn.innerHTML = `<span class="animate-spin">🌀</span> Çözümleniyor...`;

  try {
    const res = await fetch(`${API_BASE}/transactions/nlp-parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, auto_save: false })
    });

    const data = await res.json();
    pendingNLPResult = data;
    pendingNLPResult.raw_text = text;

    document.getElementById('nlp-modal-explanation').textContent = data.explanation || 'Metin başarıyla çözümlendi.';
    document.getElementById('nlp-confirm-amount').value = data.amount;
    document.getElementById('nlp-confirm-category').value = data.category;
    document.getElementById('nlp-confirm-date').value = data.date;
    document.getElementById('nlp-confirm-payment').value = data.payment_method;

    openModal('modal-nlp-confirm');
    input.value = '';
  } catch (err) {
    console.error('NLP error:', err);
    showToast('Doğal dil işleme hatası oluştu', '⚠️');
  } finally {
    btn.innerHTML = `<span>✨ Akıllı Algıla</span>`;
  }
}

async function saveConfirmedNLPTransaction() {
  if (!pendingNLPResult) return;

  const payload = {
    date: document.getElementById('nlp-confirm-date').value,
    type: pendingNLPResult.type,
    category: document.getElementById('nlp-confirm-category').value,
    amount: parseFloat(document.getElementById('nlp-confirm-amount').value),
    description: pendingNLPResult.description || 'Doğal Dil Girişi',
    payment_method: document.getElementById('nlp-confirm-payment').value,
    account_id: pendingNLPResult.suggested_account_id,
    credit_card_id: pendingNLPResult.suggested_credit_card_id,
    is_nlp_generated: 1,
    raw_input: pendingNLPResult.raw_text
  };

  try {
    const res = await authFetch(`${API_BASE}/transactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      closeModal('modal-nlp-confirm');
      showToast(`${formatTRY(payload.amount)} başarıyla kaydedildi!`, '✅');
      await refreshAllData();
    }
  } catch (err) {
    console.error('Error saving NLP transaction:', err);
  }
}

// ==========================================
// 6. AI FINANCIAL COACH (MODULE 5)
// ==========================================
async function loadAIChatHistory() {
  try {
    const [histRes, scoreRes] = await Promise.all([
      authFetch(`${API_BASE}/ai/history`),
      authFetch(`${API_BASE}/ai/score`)
    ]);

    const history = await histRes.json();
    const scoreData = await scoreRes.json();

    const score = scoreData.financial_health_score !== undefined ? scoreData.financial_health_score : 100;
    document.getElementById('sidebar-health-score').textContent = `${score}/100`;
    document.getElementById('sidebar-health-bar').style.width = `${score}%`;
    document.getElementById('ai-coach-health-score').textContent = `${score}/100`;

    const chatContainer = document.getElementById('ai-chat-messages');
    if (!chatContainer) return;

    if (history.length === 0) {
      chatContainer.innerHTML = `
        <div class="flex gap-3 items-start">
          <div class="w-8 h-8 rounded-xl bg-indigo-600/30 text-indigo-400 flex items-center justify-center shrink-0 border border-indigo-500/30">
            <i data-lucide="bot" class="w-4 h-4"></i>
          </div>
          <div class="glass-panel p-4 rounded-2xl bg-dark-800/80 max-w-xl text-xs text-gray-200 leading-relaxed border border-white/10 space-y-2">
            <p class="font-bold text-white">👋 Merhaba! Ben Finans Koçun.</p>
            <p>Banka hesaplarınızı ve kredi kartlarınızı ekledikçe size özel bütçe stratejileri, ekstre ödeme hatırlatmaları ve nakit akış öngörüleri üreteceğim.</p>
          </div>
        </div>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    chatContainer.innerHTML = history.map(msg => {
      const isUser = msg.role === 'user';
      return `
        <div class="flex gap-3 items-start ${isUser ? 'flex-row-reverse' : ''}">
          <div class="w-8 h-8 rounded-xl ${isUser ? 'bg-emerald-600/30 text-emerald-400 border-emerald-500/30' : 'bg-indigo-600/30 text-indigo-400 border-indigo-500/30'} flex items-center justify-center shrink-0 border">
            <i data-lucide="${isUser ? 'user' : 'bot'}" class="w-4 h-4"></i>
          </div>
          <div class="glass-panel p-4 rounded-2xl ${isUser ? 'bg-emerald-950/20 border-emerald-500/20' : 'bg-dark-800/90 border-white/10'} max-w-xl text-xs text-gray-200 leading-relaxed whitespace-pre-wrap">
            ${formatMarkdownText(msg.message)}
          </div>
        </div>
      `;
    }).join('');

    scrollAIChatToBottom();
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error('Error loading AI history:', err);
  }
}

function sendQuickAICoachPrompt(text) {
  const input = document.getElementById('ai-coach-input');
  if (input) {
    input.value = text;
    handleAICoachSubmit(new Event('submit'));
  }
}

async function handleAICoachSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById('ai-coach-input');
  const text = input.value.trim();
  if (!text) return;

  const chatContainer = document.getElementById('ai-chat-messages');

  chatContainer.innerHTML += `
    <div class="flex gap-3 items-start flex-row-reverse fade-in">
      <div class="w-8 h-8 rounded-xl bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 flex items-center justify-center shrink-0">
        <i data-lucide="user" class="w-4 h-4"></i>
      </div>
      <div class="glass-panel p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/20 max-w-xl text-xs text-gray-200">
        ${text}
      </div>
    </div>
  `;
  input.value = '';
  scrollAIChatToBottom();

  const typingId = `typing-${Date.now()}`;
  chatContainer.innerHTML += `
    <div id="${typingId}" class="flex gap-3 items-start fade-in">
      <div class="w-8 h-8 rounded-xl bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 flex items-center justify-center shrink-0">
        <i data-lucide="bot" class="w-4 h-4"></i>
      </div>
      <div class="glass-panel p-3.5 rounded-2xl bg-dark-800 border border-white/10 text-xs text-gray-400 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
        <span>Finansal verileriniz analiz ediliyor...</span>
      </div>
    </div>
  `;
  scrollAIChatToBottom();
  if (window.lucide) lucide.createIcons();

  try {
    const res = await authFetch(`${API_BASE}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    const data = await res.json();
    const typingEl = document.getElementById(typingId);
    if (typingEl) typingEl.remove();

    chatContainer.innerHTML += `
      <div class="flex gap-3 items-start fade-in">
        <div class="w-8 h-8 rounded-xl bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 flex items-center justify-center shrink-0">
          <i data-lucide="bot" class="w-4 h-4"></i>
        </div>
        <div class="glass-panel p-4 rounded-2xl bg-dark-800/90 border border-white/10 max-w-xl text-xs text-gray-200 leading-relaxed whitespace-pre-wrap">
          ${formatMarkdownText(data.reply)}
        </div>
      </div>
    `;

    if (data.financial_health_score !== undefined) {
      document.getElementById('sidebar-health-score').textContent = `${data.financial_health_score}/100`;
      document.getElementById('sidebar-health-bar').style.width = `${data.financial_health_score}%`;
      document.getElementById('ai-coach-health-score').textContent = `${data.financial_health_score}/100`;
    }

    scrollAIChatToBottom();
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error('AI chat error:', err);
    const typingEl = document.getElementById(typingId);
    if (typingEl) typingEl.remove();
  }
}

function scrollAIChatToBottom() {
  const container = document.getElementById('ai-chat-messages');
  if (container) {
    setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
  }
}

function formatMarkdownText(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-bold">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="text-gray-300">$1</em>');
}

// ==========================================
// 7. MODALS & SUBMISSIONS
// ==========================================
function populateTransactionModalSelectors() {
  const accSelect = document.getElementById('manual-account-id');
  const cardSelect = document.getElementById('manual-card-id');

  if (accSelect) {
    if (!accountsList || accountsList.length === 0) {
      accSelect.innerHTML = '<option value="">Kayıtlı banka hesabı bulunmuyor</option>';
    } else {
      accSelect.innerHTML = accountsList.map(a => 
        `<option value="${a.id}">${a.bank_name || 'Banka'} - ${a.name} (Bakiye: ${formatTRY(a.balance_try || a.balance)})</option>`
      ).join('');
    }
  }

  if (cardSelect) {
    if (!creditCardsList || creditCardsList.length === 0) {
      cardSelect.innerHTML = '<option value="">Kayıtlı kredi kartı bulunmuyor</option>';
    } else {
      cardSelect.innerHTML = creditCardsList.map(c => 
        `<option value="${c.id}">${c.bank_name} - ${c.card_name} (Borç: ${formatTRY(c.current_debt)})</option>`
      ).join('');
    }
  }
}

function onManualPaymentMethodChange() {
  const method = document.getElementById('manual-payment-method')?.value || 'account';
  const groupAcc = document.getElementById('group-manual-account');
  const groupCard = document.getElementById('group-manual-card');

  if (method === 'credit_card') {
    if (groupCard) groupCard.classList.remove('hidden');
    if (groupAcc) groupAcc.classList.add('hidden');
  } else {
    if (groupAcc) groupAcc.classList.remove('hidden');
    if (groupCard) groupCard.classList.add('hidden');
  }
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove('hidden');
    setTimeout(() => {
      el.classList.remove('opacity-0');
      el.classList.add('opacity-100');
    }, 10);
  }
  if (id === 'modal-transaction') {
    populateTransactionModalSelectors();
    onManualPaymentMethodChange();
  }
  if (id === 'modal-install') {
    if (typeof detectPlatform === 'function' && typeof setInstallPlatform === 'function') {
      setInstallPlatform(detectPlatform());
    }
    const inputUrl = document.getElementById('input-mobile-live-url');
    const qrImg = document.getElementById('mobile-qr-code');
    fetch('/api/mobile/live-url')
      .then(res => res.json())
      .then(data => {
        if (data && data.url) {
          if (inputUrl) inputUrl.value = data.url;
          if (qrImg) qrImg.src = `/api/mobile/qr-code?text=${encodeURIComponent(data.url)}`;
        }
      })
      .catch(() => {
        if (inputUrl && !window.location.origin.includes('127.0.0.1')) {
          inputUrl.value = window.location.origin;
          if (qrImg) qrImg.src = `/api/mobile/qr-code?text=${encodeURIComponent(window.location.origin)}`;
        }
      });
  }
  if (window.lucide) lucide.createIcons();
}

function closeModal(id) {
  if (id === 'modal-auth' && (!authToken || !currentUser)) {
    // Auth gate cannot be closed without authenticating
    return;
  }
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('opacity-0');
    el.classList.remove('opacity-100');
    setTimeout(() => {
      el.classList.add('hidden');
    }, 150);
  }
}

let manualTransType = 'expense';
function setManualType(t) {
  manualTransType = t;
  const btnExp = document.getElementById('btn-type-expense');
  const btnInc = document.getElementById('btn-type-income');
  const labelAcc = document.getElementById('label-manual-account');
  const tipAcc = document.getElementById('tip-manual-account');

  if (t === 'expense') {
    btnExp.className = 'py-2 rounded-xl font-semibold text-center border border-rose-500/30 bg-rose-500/20 text-rose-400';
    btnInc.className = 'py-2 rounded-xl font-semibold text-center border border-white/10 bg-white/5 text-gray-400';
    if (labelAcc) labelAcc.textContent = 'Harcamanın Düşüleceği Vadesiz Banka Hesabı';
    if (tipAcc) tipAcc.textContent = 'Gider kaydedildiğinde seçilen hesabın bakiyesi anında otomatik düşer.';
  } else {
    btnInc.className = 'py-2 rounded-xl font-semibold text-center border border-emerald-500/30 bg-emerald-500/20 text-emerald-400';
    btnExp.className = 'py-2 rounded-xl font-semibold text-center border border-white/10 bg-white/5 text-gray-400';
    if (labelAcc) labelAcc.textContent = 'Gelirin Yatacağı Vadesiz Banka Hesabı';
    if (tipAcc) tipAcc.textContent = 'Gelir kaydedildiğinde seçilen hesabın bakiyesi anında otomatik artar.';
  }
}

async function handleManualTransactionSubmit(e) {
  e.preventDefault();
  const method = document.getElementById('manual-payment-method').value;
  const accIdVal = document.getElementById('manual-account-id')?.value;
  const cardIdVal = document.getElementById('manual-card-id')?.value;

  const payload = {
    date: document.getElementById('manual-date').value,
    type: manualTransType,
    category: document.getElementById('manual-category').value,
    amount: parseFloat(document.getElementById('manual-amount').value),
    description: document.getElementById('manual-description').value,
    payment_method: method,
    account_id: (method === 'credit_card' ? null : (parseInt(accIdVal) || null)),
    credit_card_id: (method === 'credit_card' ? (parseInt(cardIdVal) || null) : null),
    emotion_tag: document.getElementById('manual-emotion-tag')?.value || 'essential'
  };

  try {
    const res = await authFetch(`${API_BASE}/transactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      closeModal('modal-transaction');
      const actionText = manualTransType === 'income' ? 'Gelir hesaba yansıtıldı ve bakiye arttı' : 'Gider hesaptan düşüldü ve bakiye güncellendi';
      showToast(`${actionText}!`, '💰');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'İşlem eklenemedi', '⚠️');
    }
  } catch (err) {
    console.error('Error saving transaction:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}


// New Account / Bank Submission
async function handleNewAccountSubmit(e) {
  e.preventDefault();
  const bankSelect = document.getElementById('acc-bank-select');
  let bankName = bankSelect.value;
  if (bankName.includes('Diğer')) {
    bankName = document.getElementById('acc-custom-bank').value.trim() || 'Özel Banka';
  }

  const selectedOpt = bankSelect.options[bankSelect.selectedIndex];
  const bankCode = selectedOpt ? selectedOpt.getAttribute('data-code') : 'bank';

  const payload = {
    name: document.getElementById('acc-name').value,
    type: document.getElementById('acc-type').value,
    currency: document.getElementById('acc-currency').value,
    balance: parseFloat(document.getElementById('acc-balance').value),
    bank_name: bankName,
    bank_code: bankCode,
    is_active_cash: document.getElementById('acc-is-liquid').checked ? 1 : 0
  };

  const res = await authFetch(`${API_BASE}/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    closeModal('modal-account');
    showToast(`${bankName} hesabı başarıyla eklendi!`, '🏦');
    await refreshAllData();
  }
}

// New Credit Card Submission with Timing
async function handleNewCreditCardSubmit(e) {
  e.preventDefault();
  const bankSelect = document.getElementById('card-bank-select');
  let bankName = bankSelect.value;
  if (bankName.includes('Diğer')) {
    bankName = document.getElementById('card-custom-bank').value.trim() || 'Özel Banka';
  }

  const selectedOpt = bankSelect.options[bankSelect.selectedIndex];
  const bankCode = selectedOpt ? selectedOpt.getAttribute('data-code') : 'card';

  const payload = {
    bank_name: bankName,
    bank_code: bankCode,
    card_name: document.getElementById('card-name').value,
    total_limit: parseFloat(document.getElementById('card-limit').value),
    statement_debt: parseFloat(document.getElementById('card-statement-debt').value) || 0.0,
    current_debt: parseFloat(document.getElementById('card-debt').value) || 0.0,
    cutoff_day: parseInt(document.getElementById('card-cutoff').value),
    due_day: parseInt(document.getElementById('card-due').value)
  };

  const res = await authFetch(`${API_BASE}/credits/cards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    closeModal('modal-credit-card');
    showToast(`${bankName} kartı ve ödeme takvimi kaydedildi!`, '💳');
    await refreshAllData();
  }
}

// New Loan Submission
async function handleNewLoanSubmit(e) {
  e.preventDefault();
  const bankSelect = document.getElementById('loan-bank-select');
  const bankName = bankSelect ? bankSelect.value : 'Banka';

  const payload = {
    bank_name: bankName,
    loan_title: document.getElementById('loan-title').value,
    total_amount: parseFloat(document.getElementById('loan-total').value),
    monthly_installment: parseFloat(document.getElementById('loan-monthly').value),
    remaining_installments: parseInt(document.getElementById('loan-rem').value),
    total_installments: parseInt(document.getElementById('loan-total-inst').value),
    due_day: parseInt(document.getElementById('loan-due-day').value)
  };

  const res = await authFetch(`${API_BASE}/credits/loans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    closeModal('modal-loan');
    showToast('Kredi taksiti başarıyla eklendi', '🏦');
    await refreshAllData();
  }
}

// New Recurring Rule
async function handleNewRecurringSubmit(e) {
  e.preventDefault();
  const payload = {
    title: document.getElementById('rec-title').value,
    type: document.getElementById('rec-type').value,
    category: document.getElementById('rec-category').value,
    amount: parseFloat(document.getElementById('rec-amount').value),
    day_of_month: parseInt(document.getElementById('rec-day').value),
    is_active: 1
  };

  const res = await authFetch(`${API_BASE}/transactions/recurring`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    closeModal('modal-recurring');
    showToast('Düzenli ödeme kuralı eklendi', '🔁');
    await refreshAllData();
  }
}

// ==========================================
// UTILITIES
// ==========================================
function formatTRY(num) {
  if (num === null || num === undefined) return '0 ₺';
  return `${Number(num).toLocaleString('tr-TR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ₺`;
}

function formatCurrency(num, curr) {
  if (curr === 'TRY') return formatTRY(num);
  if (curr === 'USD') return `$${Number(num).toLocaleString('en-US')}`;
  if (curr === 'EUR') return `€${Number(num).toLocaleString('de-DE')}`;
  if (curr === 'GAU') return `${Number(num).toLocaleString('tr-TR')} GAU`;
  return `${num} ${curr}`;
}

function showToast(msg, icon = '✨') {
  const toast = document.getElementById('toast');
  document.getElementById('toast-msg').textContent = msg;
  document.getElementById('toast-icon').textContent = icon;
  toast.classList.remove('translate-y-20', 'opacity-0');
  setTimeout(() => {
    toast.classList.add('translate-y-20', 'opacity-0');
  }, 3500);
}

// ==========================================
// ITEM DELETIONS & QUICK EDITS
// ==========================================
async function promptDeleteAccount(accountId, accountName) {
  if (!confirm(`"${accountName}" banka hesabını silmek istediğinize emin misiniz?`)) return;

  try {
    const res = await authFetch(`${API_BASE}/accounts/${accountId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast(`"${accountName}" hesabı başarıyla silindi.`, '🗑️');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Hesap silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Delete account error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function promptEditAccountBalance(accountId, accountName, currentBalance) {
  const newBalStr = prompt(`"${accountName}" için yeni bakiye tutarını girin (₺):`, currentBalance);
  if (newBalStr === null) return;
  const newBalance = parseFloat(newBalStr);
  if (isNaN(newBalance)) {
    showToast('Geçersiz tutar girdiniz', '⚠️');
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/accounts/${accountId}/balance?new_balance=${newBalance}`, {
      method: 'PUT'
    });

    if (res.ok) {
      showToast(`"${accountName}" bakiyesi güncellendi.`, '🏦');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Bakiye güncellenemedi', '⚠️');
    }
  } catch (err) {
    console.error('Update balance error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function promptDeleteCreditCard(cardId, cardName) {
  if (!confirm(`"${cardName}" kredi kartını ve bu karta ait tüm geçmiş ekstreleri silmek istediğinize emin misiniz?`)) return;

  try {
    const res = await authFetch(`${API_BASE}/credits/cards/${cardId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast(`"${cardName}" kartı silindi.`, '🗑️');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Kart silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Delete card error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function promptDeleteLoan(loanId, loanTitle) {
  if (!confirm(`"${loanTitle}" kredisini silmek istediğinize emin misiniz?`)) return;

  try {
    const res = await authFetch(`${API_BASE}/credits/loans/${loanId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast(`"${loanTitle}" kredisi silindi.`, '🗑️');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Kredi silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Delete loan error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function promptDeleteTransaction(transId, description) {
  if (!confirm(`"${description}" işlemini silmek istediğinize emin misiniz?`)) return;

  try {
    const res = await authFetch(`${API_BASE}/transactions/${transId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast('İşlem silindi.', '🗑️');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'İşlem silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Delete transaction error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function promptDeleteRecurring(itemId, title) {
  if (!confirm(`"${title}" düzenli ödeme kuralını silmek istediğinize emin misiniz?`)) return;

  try {
    const res = await authFetch(`${API_BASE}/transactions/recurring/${itemId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast('Düzenli ödeme kuralı silindi.', '🗑️');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Kural silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Delete recurring error:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

// ==========================================
// 6. SUPER ADMIN & AUDIT PANEL
// ==========================================
let adminUsersList = [];

async function loadAdminDashboard() {
  if (!currentUser || !currentUser.is_admin) return;

  try {
    // 1. Overview KPIs
    const overRes = await authFetch(`${API_BASE}/admin/overview`);
    if (overRes.ok) {
      const over = await overRes.json();
      const elUsers = document.getElementById('admin-kpi-users');
      const elAssets = document.getElementById('admin-kpi-assets');
      const elDebt = document.getElementById('admin-kpi-debt');
      const elNetWorth = document.getElementById('admin-kpi-networth');

      if (elUsers) elUsers.textContent = over.total_users;
      if (elAssets) elAssets.textContent = formatTRY(over.total_system_assets_try);
      if (elDebt) elDebt.textContent = formatTRY(over.total_system_card_debt_try + over.total_system_loan_debt_try);
      if (elNetWorth) elNetWorth.textContent = formatTRY(over.total_system_net_worth_try);
    }

    // 2. Users Table
    const usersRes = await authFetch(`${API_BASE}/admin/users`);
    if (usersRes.ok) {
      adminUsersList = await usersRes.json();
      renderAdminUsersTable(adminUsersList);
    }
  } catch (err) {
    console.error('Error loading admin dashboard:', err);
    showToast('Yönetici verileri yüklenirken hata oluştu.', '⚠️');
  }
}

function renderAdminUsersTable(users) {
  const tbody = document.getElementById('admin-users-tbody');
  if (!tbody) return;

  if (!users || users.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="p-8 text-center text-gray-400">
          Kayıtlı kullanıcı bulunamadı.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = users.map(u => {
    const isCurrent = currentUser && currentUser.id === u.id;
    const roleBadge = u.is_admin
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">👑 Yönetici</span>`
      : `<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-500/10 text-gray-400 border border-white/10">👤 Kullanıcı</span>`;

    const netClass = u.net_worth_try >= 0 ? 'text-emerald-400' : 'text-rose-400';
    const regDate = u.created_at ? u.created_at.split(' ')[0] : '-';

    return `
      <tr class="hover:bg-white/5 transition">
        <td class="p-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-full ${u.is_admin ? 'bg-amber-500/20 text-amber-300' : 'bg-indigo-600/30 text-indigo-300'} flex items-center justify-center font-bold text-xs shrink-0">
              ${u.full_name ? u.full_name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div>
              <div class="font-bold text-white text-xs">${u.full_name} ${isCurrent ? '<span class="text-indigo-400 text-[10px]">(Siz)</span>' : ''}</div>
              <div class="text-[10px] text-gray-400 font-mono">${u.email}</div>
            </div>
          </div>
        </td>
        <td class="p-4">${roleBadge}</td>
        <td class="p-4 text-gray-400 text-xs">${regDate}</td>
        <td class="p-4">
          <div class="font-mono text-emerald-400 font-bold">${formatTRY(u.total_assets_try)}</div>
          <div class="text-[10px] text-gray-400">${u.accounts_count} Banka Hesabı</div>
        </td>
        <td class="p-4">
          <div class="font-mono text-rose-400 font-bold">${formatTRY(u.total_debt_try)}</div>
          <div class="text-[10px] text-gray-400">${u.cards_count} Kart, ${u.loans_count} Kredi</div>
        </td>
        <td class="p-4 font-mono font-bold ${netClass}">
          ${formatTRY(u.net_worth_try)}
        </td>
        <td class="p-4 text-right">
          <div class="flex items-center justify-end gap-1.5">
            <button onclick="openAdminUserDetail(${u.id})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 transition flex items-center gap-1">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              <span>İncele</span>
            </button>
            ${!isCurrent ? `
              <button onclick="handleAdminDeleteUser(${u.id}, '${u.full_name}')" class="p-1.5 rounded-lg text-xs text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 transition" title="Kullanıcıyı Sil">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function filterAdminUsersTable() {
  const query = (document.getElementById('admin-search-input')?.value || '').toLowerCase().trim();
  if (!query) {
    renderAdminUsersTable(adminUsersList);
    return;
  }
  const filtered = adminUsersList.filter(u =>
    (u.full_name && u.full_name.toLowerCase().includes(query)) ||
    (u.email && u.email.toLowerCase().includes(query))
  );
  renderAdminUsersTable(filtered);
}

async function openAdminUserDetail(userId) {
  try {
    const res = await authFetch(`${API_BASE}/admin/users/${userId}`);
    if (!res.ok) {
      showToast('Kullanıcı detayları alınamadı', '⚠️');
      return;
    }

    const data = await res.json();
    const u = data.user;

    document.getElementById('admin-detail-user-name').textContent = u.full_name;
    document.getElementById('admin-detail-user-email').textContent = u.email;
    document.getElementById('admin-detail-user-badge').textContent = u.is_admin ? 'Süper Yönetici' : 'Standart Kullanıcı';
    document.getElementById('admin-detail-total-assets').textContent = formatTRY(u.total_assets_try);
    document.getElementById('admin-detail-total-debt').textContent = formatTRY(u.total_debt_try);
    document.getElementById('admin-detail-net-worth').textContent = formatTRY(u.net_worth_try);

    // Accounts
    const accContainer = document.getElementById('admin-detail-accounts-container');
    if (data.accounts.length === 0) {
      accContainer.innerHTML = '<div class="p-3 text-gray-500 italic bg-white/5 rounded-xl">Banka hesabı bulunmuyor.</div>';
    } else {
      accContainer.innerHTML = data.accounts.map(a => `
        <div class="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">
              <i data-lucide="landmark" class="w-3.5 h-3.5"></i>
            </div>
            <div>
              <div class="font-bold text-white text-xs">${a.bank_name || 'Banka'} - ${a.name}</div>
              <div class="text-[10px] text-gray-400 capitalize">${a.type} • ${a.currency}</div>
            </div>
          </div>
          <div class="font-mono font-bold text-emerald-400 text-xs">${formatTRY(a.balance_try)}</div>
        </div>
      `).join('');
    }

    // Credit Cards
    const cardContainer = document.getElementById('admin-detail-cards-container');
    if (data.credit_cards.length === 0) {
      cardContainer.innerHTML = '<div class="p-3 text-gray-500 italic bg-white/5 rounded-xl">Kredi kartı bulunmuyor.</div>';
    } else {
      cardContainer.innerHTML = data.credit_cards.map(c => `
        <div class="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs">
              <i data-lucide="credit-card" class="w-3.5 h-3.5"></i>
            </div>
            <div>
              <div class="font-bold text-white text-xs">${c.bank_name} ${c.card_name}</div>
              <div class="text-[10px] text-gray-400">Limit: ${formatTRY(c.total_limit)} • Kesim: ${c.cutoff_day} • Son Ödeme: ${c.due_day}</div>
            </div>
          </div>
          <div class="text-right">
            <div class="font-mono font-bold text-rose-400 text-xs">Borç: ${formatTRY(c.total_debt_load)}</div>
            <div class="text-[10px] text-gray-400">Ekstre: ${formatTRY(c.statement_debt)}</div>
          </div>
        </div>
      `).join('');
    }

    // Loans
    const loanContainer = document.getElementById('admin-detail-loans-container');
    if (data.loans.length === 0) {
      loanContainer.innerHTML = '<div class="p-3 text-gray-500 italic bg-white/5 rounded-xl">Kredi bulunmuyor.</div>';
    } else {
      loanContainer.innerHTML = data.loans.map(l => `
        <div class="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs">
              <i data-lucide="banknote" class="w-3.5 h-3.5"></i>
            </div>
            <div>
              <div class="font-bold text-white text-xs">${l.bank_name} - ${l.loan_title}</div>
              <div class="text-[10px] text-gray-400">Aylık: ${formatTRY(l.monthly_installment)} • Kalan: ${l.remaining_installments}/${l.total_installments} Taksit</div>
            </div>
          </div>
          <div class="font-mono font-bold text-amber-400 text-xs">${formatTRY(l.remaining_principal)}</div>
        </div>
      `).join('');
    }

    // Transactions
    const txContainer = document.getElementById('admin-detail-tx-container');
    if (data.transactions.length === 0) {
      txContainer.innerHTML = '<div class="p-3 text-gray-500 italic bg-white/5 rounded-xl">İşlem kaydı bulunmuyor.</div>';
    } else {
      txContainer.innerHTML = data.transactions.slice(0, 10).map(t => `
        <div class="flex items-center justify-between p-2.5 rounded-xl bg-white/5 border border-white/5 text-xs">
          <div>
            <div class="font-bold text-white">${t.description}</div>
            <div class="text-[10px] text-gray-400">${t.date} • ${t.category}</div>
          </div>
          <div class="font-mono font-bold ${t.type === 'income' ? 'text-emerald-400' : 'text-rose-400'}">
            ${t.type === 'income' ? '+' : '-'}${formatTRY(t.amount)}
          </div>
        </div>
      `).join('');
    }

    if (window.lucide) lucide.createIcons();
    openModal('modal-admin-user-detail');
  } catch (err) {
    console.error('Error opening user detail:', err);
    showToast('Kullanıcı ayrıntıları yüklenemedi', '⚠️');
  }
}

async function handleAdminDeleteUser(userId, userName) {
  if (!confirm(`"${userName}" kullanıcısını ve bu kullanıcıya ait TÜM banka hesaplarını, kartları ve hareketleri kalıcı olarak silmek istiyor musunuz?`)) return;

  try {
    const res = await authFetch(`${API_BASE}/admin/users/${userId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast(`Kullanıcı (${userName}) silindi.`, '🗑️');
      await loadAdminDashboard();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Kullanıcı silinemedi', '⚠️');
    }
  } catch (err) {
    console.error('Admin delete user error:', err);
    showToast('Sunucu bağlantı hatası', '⚠️');
  }
}

// ==========================================
// PWA & SERVICE WORKER SUPPORT
// ==========================================
let deferredPrompt = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then(reg => {
        console.log('✅ ServiceWorker registered with scope:', reg.scope);
        // Automatically check for server updates on every app launch
        reg.update();

        reg.addEventListener('updatefound', () => {
          const newWorker = reg.installing;
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                console.log('📲 Yeni sürüm yüklendi, arayüz güncelleniyor...');
                showToast('Uygulama son sürüme güncellendi! 🚀', '✨');
              }
            });
          }
        });
      })
      .catch(err => {
        console.warn('⚠️ ServiceWorker registration note:', err);
      });
  });

  // Reload page once when new service worker takes control
  let refreshing = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!refreshing) {
      refreshing = true;
      window.location.reload();
    }
  });
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  console.log('📲 PWA beforeinstallprompt captured');
  const installBtn = document.getElementById('sidebar-install-btn');
  if (installBtn) {
    installBtn.classList.add('ring-2', 'ring-emerald-500/50', 'animate-pulse');
  }
});

window.addEventListener('appinstalled', () => {
  console.log('🎉 Finans Koçun was successfully installed!');
  deferredPrompt = null;
  localStorage.setItem('smartfin_pwa_installed', 'true');
  syncInstallButtonsVisibility();
  showToast('Finans Koçun telefonunuza başarıyla yüklendi!', '🚀');
  closeModal('modal-install');
});

function detectPlatform() {
  const ua = navigator.userAgent || navigator.vendor || window.opera || '';
  if (/iPad|iPhone|iPod/.test(ua) && !window.MSStream) {
    return 'apple';
  }
  if (/Android/i.test(ua)) {
    return 'android';
  }
  return 'windows';
}

function setInstallPlatform(platform) {
  const platforms = ['apple', 'android', 'windows'];
  platforms.forEach(p => {
    const pane = document.getElementById(`install-pane-${p}`);
    const tabBtn = document.getElementById(`tab-btn-${p}`);
    if (pane) {
      if (p === platform) {
        pane.classList.remove('hidden');
      } else {
        pane.classList.add('hidden');
      }
    }
    if (tabBtn) {
      if (p === platform) {
        tabBtn.className = 'py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 bg-white/15 text-white shadow-sm';
      } else {
        tabBtn.className = 'py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 text-gray-400 hover:text-white';
      }
    }
  });
  if (window.lucide) lucide.createIcons();
}

function handleAndroidInstall() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        localStorage.setItem('smartfin_pwa_installed', 'true');
        syncInstallButtonsVisibility();
        showToast('Finans Koçun Android telefonunuza yükleniyor...', '📲');
        closeModal('modal-install');
      } else {
        showToast('Yükleme iptal edildi.', 'ℹ️');
      }
      deferredPrompt = null;
    });
  } else {
    const guideBox = document.getElementById('android-step-guide');
    if (guideBox) {
      guideBox.classList.add('ring-2', 'ring-emerald-400', 'bg-emerald-500/10');
      guideBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      setTimeout(() => {
        guideBox.classList.remove('ring-2', 'ring-emerald-400', 'bg-emerald-500/10');
      }, 3500);
    }
    const isAndroid = /Android/i.test(navigator.userAgent || '');
    if (isAndroid) {
      showToast("Chrome sağ üst köşedeki (⋮) menüden 'Uygulamayı Yükle'ye dokunun.", '🤖');
    } else {
      showToast("Android telefonunuzdan bu bağlantıyı açarak doğrudan ana ekranınıza kurabilirsiniz.", 'ℹ️');
    }
  }
}

function triggerAppInstall() {
  if (isAppInstalled()) {
    showToast('Uygulama zaten cihazınızda kurulu!', '✅');
    return;
  }
  const platform = detectPlatform();
  setInstallPlatform(platform);
  openModal('modal-install');
}

function triggerPwaPrompt() {
  closeModal('modal-install');
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt = null;
  } else {
    showToast('Tarayıcınızın adres çubuğundaki yükleme simgesine tıklayabilirsiniz.', 'ℹ️');
  }
}

// ==========================================
// COMMERCIAL PRICING & SUBSCRIPTION (SAAS)
// ==========================================
function openPricingModal() {
  const currentPlan = (currentUser?.plan || 'free').toLowerCase();
  
  const btnFree = document.getElementById('btn-select-free');
  const btnPro = document.getElementById('btn-select-pro');
  const btnVip = document.getElementById('btn-select-vip');

  if (btnFree) {
    if (currentPlan === 'free') {
      btnFree.textContent = 'Mevcut Planınız (Aktif)';
      btnFree.className = 'w-full py-2.5 rounded-xl font-bold text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 cursor-default';
    } else {
      btnFree.textContent = 'Başlangıç Planına Dön';
      btnFree.className = 'w-full py-2.5 rounded-xl font-semibold text-xs bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 transition';
    }
  }

  if (btnPro) {
    if (currentPlan === 'pro') {
      btnPro.textContent = 'Mevcut Planınız (Aktif PRO)';
      btnPro.className = 'w-full py-2.5 rounded-xl font-bold text-xs bg-emerald-500/30 text-emerald-300 border border-emerald-500/50 cursor-default shadow-lg';
    } else {
      btnPro.textContent = "Hemen PRO'ya Geç (99 ₺)";
      btnPro.className = 'w-full py-2.5 rounded-xl font-bold text-xs bg-gradient-to-r from-emerald-500 to-indigo-600 hover:from-emerald-400 hover:to-indigo-500 text-white shadow-lg shadow-indigo-500/25 transition-all';
    }
  }

  if (btnVip) {
    if (currentPlan === 'vip') {
      btnVip.textContent = 'Mevcut Planınız (Aktif VIP)';
      btnVip.className = 'w-full py-2.5 rounded-xl font-bold text-xs bg-amber-500/30 text-amber-300 border border-amber-500/50 cursor-default shadow-lg';
    } else {
      btnVip.textContent = 'Yıllık VIP Avantajı (799 ₺)';
      btnVip.className = 'w-full py-2.5 rounded-xl font-bold text-xs bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white shadow-lg shadow-amber-500/20 transition-all';
    }
  }

  openModal('modal-pricing');
}

function startCheckout(tier, planName, price) {
  if (!currentUser) {
    closeModal('modal-pricing');
    showToast('Öncelikle giriş yapmanız veya kayıt olmanız gerekmektedir.', '🔒');
    openModal('modal-auth');
    return;
  }

  document.getElementById('checkout-tier').value = tier;
  document.getElementById('checkout-plan-title').textContent = `${planName} • ${price} ₺`;
  document.getElementById('checkout-summary-name').textContent = planName;
  document.getElementById('checkout-summary-price').textContent = `${price} ₺`;
  
  const cardHolderInput = document.getElementById('checkout-cardholder');
  if (cardHolderInput && currentUser.full_name) {
    cardHolderInput.value = currentUser.full_name;
  }

  closeModal('modal-pricing');
  openModal('modal-checkout');
}

function formatCardNumber(input) {
  let val = input.value.replace(/\D/g, '');
  let formatted = '';
  for (let i = 0; i < val.length; i++) {
    if (i > 0 && i % 4 === 0) formatted += ' ';
    formatted += val[i];
  }
  input.value = formatted.substring(0, 19);
}

function formatExpiry(input) {
  let val = input.value.replace(/\D/g, '');
  if (val.length >= 2) {
    input.value = val.substring(0, 2) + '/' + val.substring(2, 4);
  } else {
    input.value = val;
  }
}

async function selectFreePlan() {
  const currentPlan = (currentUser?.plan || 'free').toLowerCase();
  if (currentPlan === 'free') {
    showToast('Zaten ücretsiz Başlangıç paketindesiniz.', 'ℹ️');
    return;
  }
  if (!confirm('Planınızı ücretsiz Başlangıç seviyesine düşürmek istediğinize emin misiniz?')) {
    return;
  }
  try {
    const res = await authFetch(`${API_BASE}/auth/upgrade-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: 'free' })
    });
    if (res.ok) {
      const updatedUser = await res.json();
      currentUser = updatedUser;
      localStorage.setItem('smartfin_user', JSON.stringify(currentUser));
      updateAuthUI();
      closeModal('modal-pricing');
      showToast('Planınız Başlangıç olarak güncellendi.', 'ℹ️');
    }
  } catch (err) {
    showToast('Plan güncellenirken hata oluştu', '⚠️');
  }
}

async function handleCheckoutSubmit(event) {
  event.preventDefault();
  const tier = document.getElementById('checkout-tier').value;
  const submitBtn = document.getElementById('btn-submit-payment');
  const submitBtnText = document.getElementById('btn-submit-payment-text');

  if (submitBtn) submitBtn.disabled = true;
  if (submitBtnText) submitBtnText.textContent = '3D Secure Doğrulanıyor...';

  try {
    await new Promise(r => setTimeout(r, 650));

    const res = await authFetch(`${API_BASE}/auth/upgrade-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: tier })
    });

    if (res.ok) {
      const updatedUser = await res.json();
      currentUser = updatedUser;
      localStorage.setItem('smartfin_user', JSON.stringify(currentUser));
      updateAuthUI();
      closeModal('modal-checkout');
      
      const planTitle = tier === 'vip' ? 'VIP Yıllık' : 'PRO Aylık';
      showToast(`🎉 Tebrikler! ${planTitle} paketiniz başarıyla aktif edildi!`, '✨');
      await refreshAllData();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Ödeme işlenemedi, lütfen tekrar deneyin', '⚠️');
    }
  } catch (err) {
    console.error('Checkout error:', err);
    showToast('Ödeme sunucusuna bağlanılamadı', '⚠️');
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (submitBtnText) submitBtnText.textContent = 'Güvenli Öde ve Anında Aktifleştir';
  }
}

// ==========================================
// DESKTOP 1-CLICK SHORTCUT & DOWNLOAD
// ==========================================
async function handleDirectDesktopShortcut() {
  const btn = document.getElementById('btn-desktop-shortcut-action');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Masaüstü Kısayolu Kuruluyor...</span>`;
    if (window.lucide) lucide.createIcons();
  }

  try {
    // 1. Call server API to create/refresh actual Windows .lnk on user's Desktop
    const res = await fetch(`${API_BASE}/desktop/create-shortcut`, { method: 'POST' });
    const data = await res.json();

    // 2. Also trigger direct browser download of launcher file
    const downloadLink = document.createElement('a');
    downloadLink.href = `${API_BASE}/desktop/download-launcher`;
    downloadLink.download = 'Finans_Kocun_Baslat.bat';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);

    // 3. Trigger native PWA prompt if available
    if (deferredPrompt) {
      deferredPrompt.prompt();
    }

    showToast('🎉 Finans Koçun masaüstünüze kuruldu! Masaüstünüzdeki logolu simgeden başlatabilirsiniz.', '🚀');
    
    setTimeout(() => {
      closeModal('modal-install');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="check" class="w-4 h-4 text-emerald-400"></i><span>Masaüstü Kısayolu Kuruldu!</span>`;
        if (window.lucide) lucide.createIcons();
      }
    }, 1500);
  } catch (err) {
    console.error('Desktop shortcut error:', err);
    showToast('Kısayol oluşturulurken hata: ' + err.message, '⚠️');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="monitor" class="w-4 h-4"></i><span>Masaüstüme Kısayol Kur & İndir (1-Tık)</span>`;
      if (window.lucide) lucide.createIcons();
    }
  }
}

// ==========================================
// INTERACTIVE MOBILE SIMULATOR MODE
// ==========================================
let isMobileSimulatorActive = false;
function toggleMobileSimulator() {
  isMobileSimulatorActive = !isMobileSimulatorActive;
  const body = document.body;
  const toggleBtnText = document.getElementById('btn-toggle-mobile-text');
  const floatingBanner = document.getElementById('simulator-floating-banner');
  const notchBar = document.getElementById('phone-notch-bar');
  const bottomNav = document.getElementById('mobile-bottom-nav');

  if (isMobileSimulatorActive) {
    body.classList.add('mobile-simulator-mode');
    if (toggleBtnText) toggleBtnText.textContent = 'Masaüstü Görünüm';
    if (floatingBanner) floatingBanner.classList.remove('hidden');
    if (notchBar) notchBar.classList.remove('hidden');
    if (bottomNav) bottomNav.classList.remove('lg:hidden');
    showToast('📱 Akıllı telefon simülasyonu aktif edildi.', '📲');
  } else {
    body.classList.remove('mobile-simulator-mode');
    if (toggleBtnText) toggleBtnText.textContent = 'Mobil Görünüm';
    if (floatingBanner) floatingBanner.classList.add('hidden');
    if (notchBar) notchBar.classList.add('hidden');
    if (bottomNav) bottomNav.classList.add('lg:hidden');
    showToast('💻 Masaüstü geniş ekran görünümüne dönüldü.', '🖥️');
  }

  // Close sidebar drawer if open
  const sidebar = document.getElementById('sidebar');
  if (sidebar && !sidebar.classList.contains('-translate-x-full')) {
    toggleSidebar();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (window.lucide) lucide.createIcons();
}

// ==========================================
// COPY MOBILE LIVE URL HELPER
// ==========================================
function copyMobileUrl() {
  const input = document.getElementById('input-mobile-live-url');
  if (!input) return;
  input.select();
  input.setSelectionRange(0, 99999);
  navigator.clipboard.writeText(input.value).then(() => {
    const copyBtnText = document.getElementById('btn-copy-url-text');
    if (copyBtnText) copyBtnText.textContent = 'Kopyalandı! ✓';
    showToast('📱 Canlı mobil bağlantı linki panoya kopyalandı!', '📋');
    setTimeout(() => {
      if (copyBtnText) copyBtnText.textContent = 'Kopyala';
    }, 2500);
  }).catch(() => {
    showToast('Link kopyalanamadı, lütfen elle kopyalayın.', '⚠️');
  });
}

// ==========================================
// MOBILE-FIRST UX HELPERS (ACCORDION & EMOTION CHIPS)
// ==========================================
function toggleMetricsAccordion() {
  const wrapper = document.getElementById('metrics-accordion-wrapper');
  const label = document.getElementById('accordion-toggle-label');
  const icon = document.getElementById('accordion-toggle-icon');
  if (!wrapper) return;

  isMetricsAccordionExpanded = !isMetricsAccordionExpanded;
  if (isMetricsAccordionExpanded) {
    wrapper.classList.remove('hidden');
    if (label) label.textContent = 'Özeti Daralt';
    if (icon) icon.classList.add('rotate-180');
  } else {
    wrapper.classList.add('hidden');
    wrapper.classList.add('sm:block');
    if (label) label.textContent = 'Detayları Göster';
    if (icon) icon.classList.remove('rotate-180');
  }
}

function selectEmotionTag(tag) {
  const hiddenInput = document.getElementById('manual-emotion-tag');
  if (hiddenInput) hiddenInput.value = tag;

  const chipBtns = document.querySelectorAll('.emotion-chip-btn');
  chipBtns.forEach(btn => btn.classList.remove('active'));

  const activeBtn = document.getElementById(`btn-emotion-${tag}`);
  if (activeBtn) activeBtn.classList.add('active');
}

// ==========================================
// MODULE 1: KATEGORİ BAZLI BÜTÇE SINIRLARI & UYARILAR
// ==========================================
async function loadCategoryBudgets() {
  if (!authToken) return;
  try {
    const res = await authFetch(`${API_BASE}/budgets`);
    if (res.ok) {
      categoryBudgetsList = await res.json();
      renderCategoryBudgetsUI();
    }
  } catch (err) {
    console.error('Error loading category budgets:', err);
  }
}

function renderCategoryBudgetsUI() {
  const container = document.getElementById('category-budgets-container');
  if (!container) return;

  if (!categoryBudgetsList || categoryBudgetsList.length === 0) {
    container.innerHTML = `
      <div class="col-span-full p-6 rounded-2xl bg-white/5 border border-dashed border-white/10 text-center">
        <div class="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center mb-2">
          <i data-lucide="sliders-horizontal" class="w-5 h-5"></i>
        </div>
        <h4 class="text-xs font-bold text-white">Henüz Bir Kategori Limiti Belirlenmedi</h4>
        <p class="text-[11px] text-gray-400 mt-1 max-w-sm mx-auto">
          Market, Eğlence veya Yeme-İçme gibi kategorilerinize aylık tavan sınır koyarak bütçenizi kontrol altında tutun.
        </p>
        <button onclick="openBudgetLimitModal()" class="mt-3 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition inline-flex items-center gap-1.5">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i>
          <span>İlk Limiti Belirle</span>
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = categoryBudgetsList.map(b => {
    const limit = b.monthly_limit || 1;
    const spent = b.current_spent !== undefined ? b.current_spent : (b.spent_current_month || 0);
    const pct = b.percentage_spent !== undefined ? Math.round(b.percentage_spent) : Math.round((spent / limit) * 100);
    const rem = b.remaining_budget !== undefined ? b.remaining_budget : (limit - spent);

    let statusBadge = '';
    let barColor = 'bg-emerald-500';
    let borderColor = 'border-white/10';

    if (pct >= 100) {
      statusBadge = `<span class="text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/30 px-2 py-0.5 rounded-full font-bold">AŞILDI (%${pct})</span>`;
      barColor = 'bg-rose-500';
      borderColor = 'border-rose-500/30 glow-rose';
    } else if (pct >= 80) {
      statusBadge = `<span class="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full font-bold">DİKKAT (%${pct})</span>`;
      barColor = 'bg-amber-500';
      borderColor = 'border-amber-500/30 glow-amber';
    } else {
      statusBadge = `<span class="text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold">GÜVENLİ (%${pct})</span>`;
      barColor = 'bg-emerald-500';
      borderColor = 'border-white/10';
    }

    const cappedPct = Math.min(pct, 100);

    return `
      <div class="glass-panel p-4 rounded-2xl border ${borderColor} space-y-3 relative group">
        <div class="flex items-start justify-between">
          <div>
            <span class="text-xs font-bold text-white block">${b.category}</span>
            <span class="text-[10px] text-gray-400 block mt-0.5">Aylık Limit: ${formatTRY(limit)}</span>
          </div>
          <div class="flex items-center gap-1.5">
            ${statusBadge}
            <button onclick="promptDeleteBudget(${b.id}, '${b.category}')" class="p-1 text-gray-500 hover:text-rose-400 transition" title="Limiti Kaldır">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>

        <div class="space-y-1">
          <div class="flex justify-between items-center text-[11px] font-mono">
            <span class="text-gray-300">Harcanan: <strong class="text-white">${formatTRY(spent)}</strong></span>
            <span class="${rem >= 0 ? 'text-emerald-400' : 'text-rose-400'} font-semibold">
              ${rem >= 0 ? `Kalan: ${formatTRY(rem)}` : `Aşım: ${formatTRY(Math.abs(rem))}`}
            </span>
          </div>
          <div class="w-full bg-dark-950 rounded-full h-2 overflow-hidden border border-white/5">
            <div class="${barColor} h-2 rounded-full transition-all duration-500" style="width: ${cappedPct}%"></div>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function openBudgetLimitModal(category = '', limit = '') {
  const catSelect = document.getElementById('budget-category-select');
  const amtInput = document.getElementById('budget-amount-input');

  if (catSelect && categoriesList && categoriesList.length > 0) {
    catSelect.innerHTML = categoriesList
      .filter(c => c.name !== 'Maaş' && c.name !== 'Gelir')
      .map(c => `<option value="${c.name}" ${c.name === category ? 'selected' : ''}>${c.name}</option>`)
      .join('');
  }

  if (amtInput) amtInput.value = limit || '';
  openModal('modal-budget-limit');
}

async function handleSaveBudgetLimit(e) {
  e.preventDefault();
  const category = document.getElementById('budget-category-select').value;
  const limitVal = parseFloat(document.getElementById('budget-amount-input').value);

  if (!category || !limitVal) {
    showToast('Lütfen kategori ve limit tutarını girin.', '⚠️');
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/budgets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: category,
        monthly_limit: limitVal,
        warning_threshold_pct: 80.0
      })
    });

    if (res.ok) {
      closeModal('modal-budget-limit');
      showToast(`${category} için aylık ${formatTRY(limitVal)} limit kaydedildi!`, '🎯');
      await loadCategoryBudgets();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Limit kaydedilemedi', '⚠️');
    }
  } catch (err) {
    console.error('Error saving budget limit:', err);
    showToast('Bağlantı hatası oluştu', '⚠️');
  }
}

async function promptDeleteBudget(id, name) {
  if (!confirm(`"${name}" kategorisine ait bütçe limitini kaldırmak istiyor musunuz?`)) return;
  try {
    const res = await authFetch(`${API_BASE}/budgets/${id}`, { method: 'DELETE' });
    if (res.ok) {
      showToast(`${name} limiti kaldırıldı.`, '🗑️');
      await loadCategoryBudgets();
    }
  } catch (err) {
    console.error('Error deleting budget:', err);
  }
}

// ==========================================
// MODULE 2: "ABONELİK AVCISI" (SUBSCRIPTION HUNTER)
// ==========================================
async function loadSubscriptionHunter() {
  if (!authToken) return;
  try {
    const res = await authFetch(`${API_BASE}/subscriptions/detected`);
    if (res.ok) {
      subscriptionsData = await res.json();
      renderSubscriptionHunterUI();
    }
  } catch (err) {
    console.error('Error loading subscriptions:', err);
  }
}

function renderSubscriptionHunterUI() {
  if (!subscriptionsData) return;

  const elMonthly = document.getElementById('sub-hunter-monthly');
  const elAnnual = document.getElementById('sub-hunter-annual');
  const container = document.getElementById('subscriptions-container');
  const tipBanner = document.getElementById('subscriptions-tip-banner');
  const tipText = document.getElementById('subscriptions-tip-text');

  if (elMonthly) elMonthly.textContent = formatTRY(subscriptionsData.total_monthly_cost || 0);
  if (elAnnual) elAnnual.textContent = formatTRY(subscriptionsData.total_annual_cost || 0);

  if (tipBanner && tipText) {
    if (subscriptionsData.smart_tips && subscriptionsData.smart_tips.length > 0) {
      tipText.textContent = subscriptionsData.smart_tips[0];
      tipBanner.classList.remove('hidden');
    } else {
      tipBanner.classList.add('hidden');
    }
  }

  if (!container) return;

  if (!subscriptionsData.subscriptions || subscriptionsData.subscriptions.length === 0) {
    container.innerHTML = `
      <div class="col-span-full p-5 rounded-2xl bg-white/5 border border-dashed border-white/10 text-center">
        <p class="text-xs text-gray-400">Henüz düzenli çekilen bir abonelik (Netflix, Spotify, aidat vb.) tespit edilmedi.</p>
        <span class="text-[10px] text-gray-500 block mt-1">İşlem geçmişiniz genişledikçe abonelikleriniz otomatik algılanır.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = subscriptionsData.subscriptions.map(s => {
    let diffBadge = '';
    if (s.cancellation_difficulty === 'zor') {
      diffBadge = `<span class="text-[9px] bg-rose-500/20 text-rose-400 border border-rose-500/30 px-1.5 py-0.5 rounded font-semibold">İptal: Zor</span>`;
    } else if (s.cancellation_difficulty === 'orta') {
      diffBadge = `<span class="text-[9px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded font-semibold">İptal: Orta</span>`;
    } else {
      diffBadge = `<span class="text-[9px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.5 rounded font-semibold">İptal: Kolay</span>`;
    }

    return `
      <div class="p-3.5 rounded-2xl bg-dark-950/80 border border-white/10 space-y-2 hover:border-purple-500/30 transition-all">
        <div class="flex items-start justify-between">
          <div>
            <h5 class="text-xs font-bold text-white">${s.title || s.name}</h5>
            <span class="text-[10px] text-gray-400 block">${s.category}</span>
          </div>
          ${diffBadge}
        </div>

        <div class="flex items-baseline justify-between pt-1 border-t border-white/5 text-xs">
          <div>
            <span class="text-[10px] text-gray-400 block">Aylık Tutar</span>
            <span class="font-bold text-purple-300 font-mono">${formatTRY(s.amount)}</span>
          </div>
          <div class="text-right">
            <span class="text-[10px] text-gray-400 block">Yıllık Yük</span>
            <span class="font-bold text-amber-400 font-mono text-[11px]">${formatTRY(s.annual_cost)} / yıl</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

// ==========================================
// MODULE 3: HARCAMA PSİKOLOJİSİ & DAVRANIŞSAL ANALİZ
// ==========================================
async function loadSpendingPsychology() {
  if (!authToken) return;
  try {
    const res = await authFetch(`${API_BASE}/analytics/psychology`);
    if (res.ok) {
      psychologyData = await res.json();
      renderSpendingPsychologyUI();
    }
  } catch (err) {
    console.error('Error loading spending psychology:', err);
  }
}

function renderSpendingPsychologyUI() {
  if (!psychologyData) return;

  const elScore = document.getElementById('psy-health-score');
  const elVerdict = document.getElementById('psy-verdict-text');
  const elImpulsive = document.getElementById('psy-impulsive-ratio');
  const listContainer = document.getElementById('psy-breakdown-list');
  const elInsight = document.getElementById('psy-insight-text');

  if (elScore) elScore.textContent = `${psychologyData.psychological_health_score}/100`;
  if (elVerdict) elVerdict.textContent = psychologyData.health_verdict;
  if (elImpulsive) elImpulsive.textContent = `Dürtüsel Oran: %${psychologyData.impulsive_ratio}`;

  if (elInsight && psychologyData.behavioral_insights && psychologyData.behavioral_insights.length > 0) {
    elInsight.textContent = psychologyData.behavioral_insights[0];
  }

  if (!listContainer) return;

  if (!psychologyData.breakdown || psychologyData.breakdown.length === 0) {
    listContainer.innerHTML = `<p class="text-gray-500 text-[11px] py-2">Duygu etiketli harcama girildiğinde analiz burada oluşur.</p>`;
    return;
  }

  listContainer.innerHTML = psychologyData.breakdown.map(b => {
    return `
      <div class="space-y-1">
        <div class="flex justify-between items-center text-[11px]">
          <span class="text-gray-300 flex items-center gap-1.5">
            <span>${b.icon}</span>
            <span class="font-medium">${b.tag_label}</span>
          </span>
          <span class="font-mono text-gray-200">
            ${formatTRY(b.total_amount)} (%${b.percentage_of_total})
          </span>
        </div>
        <div class="w-full bg-dark-950 rounded-full h-1.5 overflow-hidden border border-white/5">
          <div class="h-1.5 rounded-full transition-all duration-500" style="width: ${b.percentage_of_total}%; background-color: ${b.color};"></div>
        </div>
      </div>
    `;
  }).join('');
}

// ==========================================
// MODULE 5: KİŞİSEL ENFLASYON ENDEKSİ
// ==========================================
async function loadPersonalInflation() {
  if (!authToken) return;
  try {
    const res = await authFetch(`${API_BASE}/analytics/personal-inflation`);
    if (res.ok) {
      personalInflationData = await res.json();
      renderPersonalInflationUI();
    }
  } catch (err) {
    console.error('Error loading personal inflation:', err);
  }
}

function renderPersonalInflationUI() {
  if (!personalInflationData) return;

  const elPersonal = document.getElementById('cpi-personal-rate');
  const elOfficial = document.getElementById('cpi-official-rate');
  const elDivergence = document.getElementById('cpi-divergence-pill');
  const driversList = document.getElementById('cpi-drivers-list');
  const hedgeTip = document.getElementById('cpi-hedge-tip');

  if (elPersonal) elPersonal.textContent = `%${personalInflationData.personal_inflation_annual_rate}`;
  if (elOfficial) elOfficial.textContent = `%${personalInflationData.official_cpi_rate}`;

  if (elDivergence) {
    const diff = personalInflationData.inflation_difference;
    if (diff > 0) {
      elDivergence.className = 'text-[10px] text-rose-400 block mt-0.5 font-semibold';
      elDivergence.textContent = `+${diff}% Resmi TÜFE'den Yüksek`;
    } else {
      elDivergence.className = 'text-[10px] text-emerald-400 block mt-0.5 font-semibold';
      elDivergence.textContent = `${diff}% Resmi TÜFE'den Düşük`;
    }
  }

  if (hedgeTip && personalInflationData.hedge_tips && personalInflationData.hedge_tips.length > 0) {
    hedgeTip.textContent = personalInflationData.hedge_tips[0];
  }

  if (!driversList) return;

  if (!personalInflationData.category_details || personalInflationData.category_details.length === 0) {
    driversList.innerHTML = `<p class="text-gray-500 text-[11px]">Harcama geçmişinizle kişisel enflasyon sepetiniz otomatik hesaplanır.</p>`;
    return;
  }

  const topDrivers = personalInflationData.category_details.slice(0, 3);
  driversList.innerHTML = topDrivers.map(d => {
    return `
      <div class="flex items-center justify-between p-2 rounded-xl bg-white/5 border border-white/5 text-[11px]">
        <div class="flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
          <span class="font-medium text-white">${d.category}</span>
          <span class="text-[10px] text-gray-500 font-mono">(Sepet: %${d.weight})</span>
        </div>
        <span class="font-mono text-amber-300 font-bold">%${d.category_inflation_rate} yıllık</span>
      </div>
    `;
  }).join('');
}

// ==========================================
// MODULE 4: "WHAT-IF" SENARYO SİMÜLATÖRÜ
// ==========================================
async function handleWhatIfSubmit(e) {
  e.preventDefault();
  const title = document.getElementById('whatif-title').value.trim();
  const amount = parseFloat(document.getElementById('whatif-amount').value);
  const installments = parseInt(document.getElementById('whatif-installments').value) || 1;
  const btn = document.getElementById('btn-run-whatif');

  if (!title || !amount) {
    showToast('Lütfen başlık ve tutar girin.', '⚠️');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin inline-block mr-1.5">⏳</span> Simüle Ediliyor...`;
  }

  try {
    const res = await authFetch(`${API_BASE}/analytics/what-if`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_title: title,
        amount: amount,
        installment_count: installments,
        scenario_type: 'expense'
      })
    });

    if (res.ok) {
      whatIfSimulationData = await res.json();
      renderWhatIfSimulationResult(whatIfSimulationData);
      renderCashFlowChart();
      showToast(`"${title}" senaryosu simüle edildi!`, '✨');
    } else {
      const err = await res.json();
      showToast(err.detail || 'Simülasyon çalıştırılamadı', '⚠️');
    }
  } catch (err) {
    console.error('What-If error:', err);
    showToast('Simülasyon bağlantı hatası', '⚠️');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5 fill-current"></i> <span>Simülasyonu Çalıştır</span>`;
      if (window.lucide) lucide.createIcons();
    }
  }
}

function renderWhatIfSimulationResult(data) {
  const card = document.getElementById('whatif-result-card');
  if (!card || !data) return;

  const badgeIcon = document.getElementById('whatif-badge-icon');
  const badge = document.getElementById('whatif-status-badge');
  const headline = document.getElementById('whatif-headline');
  const projEnd = document.getElementById('whatif-projected-end');
  const lowestDip = document.getElementById('whatif-lowest-dip');
  const recText = document.getElementById('whatif-recommendation-text');

  card.classList.remove('hidden');

  if (data.will_enter_deficit) {
    if (badge) {
      badge.textContent = 'DİKKAT: KASA AÇIĞI RİSKİ';
      badge.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30';
    }
    if (badgeIcon) {
      badgeIcon.className = 'w-8 h-8 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold';
      badgeIcon.innerHTML = `<i data-lucide="alert-triangle" class="w-4 h-4"></i>`;
    }
    if (headline) {
      headline.textContent = `${data.deficit_day ? data.deficit_day + ' tarihinde ' : ''}kasa eksiye düşebilir!`;
    }
  } else {
    if (badge) {
      badge.textContent = 'GÜVENLİ BÖLGE';
      badge.className = 'text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    }
    if (badgeIcon) {
      badgeIcon.className = 'w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold';
      badgeIcon.innerHTML = `<i data-lucide="shield-check" class="w-4 h-4"></i>`;
    }
    if (headline) {
      headline.textContent = 'Nakit akışınız bu harcamayı güvenle karşılıyor.';
    }
  }

  if (projEnd) {
    projEnd.textContent = formatTRY(data.projected_end_of_month_balance);
    projEnd.className = `font-bold ${data.projected_end_of_month_balance >= 0 ? 'text-white' : 'text-rose-400'}`;
  }

  if (lowestDip) {
    lowestDip.textContent = formatTRY(data.lowest_balance);
    lowestDip.className = `font-bold ${data.lowest_balance >= 0 ? 'text-amber-400' : 'text-rose-400'}`;
  }

  if (recText) {
    recText.textContent = data.recommendation;
  }

  if (window.lucide) lucide.createIcons();
}

function resetWhatIfSimulation() {
  whatIfSimulationData = null;
  const card = document.getElementById('whatif-result-card');
  if (card) card.classList.add('hidden');

  const titleInput = document.getElementById('whatif-title');
  const amountInput = document.getElementById('whatif-amount');
  const installmentsSelect = document.getElementById('whatif-installments');

  if (titleInput) titleInput.value = '';
  if (amountInput) amountInput.value = '';
  if (installmentsSelect) installmentsSelect.value = '1';

  renderCashFlowChart();
  showToast('Simülasyon sıfırlandı.', '🔄');
}

// ==========================================
// TELEGRAM & WHATSAPP BOT INTEGRATION
// ==========================================
let currentBotPairingCode = '';

async function loadBotStatus() {
  const launchBox = document.getElementById('bot-telegram-launch-box');
  const openLink = document.getElementById('bot-telegram-open-link');
  const btnText = document.getElementById('bot-telegram-btn-text');
  const statusBadge = document.getElementById('bot-status-badge');
  const headerText = document.getElementById('bot-status-header-text');
  const tokenInput = document.getElementById('bot-token-input');

  try {
    const res = await fetch(`${API_BASE}/bot/status`);
    if (!res.ok) return;
    const data = await res.json();

    if (data.bot_username && data.bot_url) {
      if (openLink) {
        openLink.href = data.bot_url;
        openLink.classList.remove('pointer-events-none', 'opacity-60');
      }
      if (btnText) btnText.textContent = `Telegram'da @${data.bot_username} Botunu Aç`;
      if (headerText) headerText.textContent = `Telegram: @${data.bot_username}`;
      if (statusBadge) {
        statusBadge.textContent = 'Canlı & Aktif';
        statusBadge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
      }
    } else {
      if (openLink) {
        openLink.href = '#';
        openLink.classList.add('pointer-events-none', 'opacity-60');
      }
      if (btnText) btnText.textContent = 'Telegram Bot Token Henüz Ayarlanmadı';
      if (headerText) headerText.textContent = 'Telegram Botu (Kurulum Gerekli)';
      if (statusBadge) {
        statusBadge.textContent = 'Token Bekleniyor';
        statusBadge.className = 'px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30';
      }
    }
  } catch (err) {
    console.error('Error fetching bot status:', err);
  }
}

async function loadBotPairings() {
  const container = document.getElementById('bot-pairings-list');
  if (!container || !authToken) return;

  try {
    const res = await authFetch(`${API_BASE}/bot/pairings`);
    if (!res.ok) {
      container.innerHTML = `<div class="p-2.5 rounded-xl bg-white/5 border border-white/5 text-gray-400">Henüz bağlı bir Telegram/WhatsApp hesabı bulunmuyor.</div>`;
      return;
    }
    const data = await res.json();
    const pairings = data.pairings || [];

    if (pairings.length === 0) {
      container.innerHTML = `<div class="p-2.5 rounded-xl bg-white/5 border border-white/5 text-gray-400">Henüz bağlı bir hesap yok. Yukarıdan kodunuzu girip hemen bağlayabilirsiniz.</div>`;
      return;
    }

    container.innerHTML = pairings.map(p => `
      <div class="flex items-center justify-between p-2.5 rounded-xl bg-white/5 border border-white/10 hover:border-blue-500/30 transition">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-xs uppercase">
            ${p.platform === 'telegram' ? 'TG' : 'WA'}
          </div>
          <div>
            <span class="text-white font-semibold block">${p.sender_id.startsWith('@') ? p.sender_id : '@' + p.sender_id}</span>
            <span class="text-[9px] text-gray-400 font-mono">${p.platform} • Eşlendi</span>
          </div>
        </div>
        <button onclick="deleteUserPairing(${p.id})" class="text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded-lg hover:bg-red-500/10 transition" title="Bağlantıyı Kaldır">
          Kaldır
        </button>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading bot pairings:', err);
  }
}

async function openBotConnectModal() {
  openModal('modal-bot-connect');
  const displayEl = document.getElementById('bot-display-link-code');
  const urlDisplay = document.getElementById('bot-webhook-url-display');

  if (urlDisplay) {
    urlDisplay.textContent = `${window.location.origin}/api/bot/webhook`;
  }

  loadBotStatus();
  loadBotPairings();

  if (!authToken) {
    if (displayEl) displayEl.textContent = 'GİRİŞ YAPIN';
    return;
  }

  try {
    const res = await authFetch(`${API_BASE}/bot/generate-link-code`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      currentBotPairingCode = data.code;
      if (displayEl) displayEl.textContent = data.code;
    }
  } catch (err) {
    console.error('Error getting bot link code:', err);
    if (displayEl) displayEl.textContent = 'FK-HATA';
  }
}

function copyBotLinkCode() {
  if (!currentBotPairingCode) return;
  navigator.clipboard.writeText(currentBotPairingCode).then(() => {
    const btnText = document.getElementById('copy-bot-code-text');
    if (btnText) {
      btnText.textContent = 'Kopyalandı!';
      setTimeout(() => { btnText.textContent = 'Kopyala'; }, 2000);
    }
    showToast(`Bağlantı kodu kopyalandı: ${currentBotPairingCode}`, '📋');
  });
}

function copyWebhookUrl() {
  const url = `${window.location.origin}/api/bot/webhook`;
  navigator.clipboard.writeText(url).then(() => {
    showToast('Webhook adresi kopyalandı!', '🔗');
  });
}

async function handleDirectPairSubmit(event) {
  event.preventDefault();
  const inputEl = document.getElementById('bot-code-input');
  const btnEl = document.getElementById('btn-bot-code-pair');
  const alertEl = document.getElementById('bot-pair-alert');

  const identifier = inputEl ? inputEl.value.trim() : '';
  if (!identifier) return;

  if (btnEl) btnEl.disabled = true;
  if (alertEl) {
    alertEl.className = 'p-2.5 rounded-xl text-[11px] font-medium bg-blue-900/40 text-blue-200 border border-blue-500/30';
    alertEl.textContent = 'Hesap doğrulanıyor ve eşleştiriliyor...';
    alertEl.classList.remove('hidden');
  }

  try {
    const res = await authFetch(`${API_BASE}/bot/pair-direct`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (alertEl) {
        alertEl.className = 'p-2.5 rounded-xl text-[11px] font-medium bg-emerald-900/40 text-emerald-200 border border-emerald-500/30';
        alertEl.textContent = data.message || 'Hesabınız başarıyla bağlandı!';
      }
      if (inputEl) inputEl.value = '';
      showToast('Telegram hesabınız başarıyla bağlandı!', '✅');
      loadBotPairings();
    } else {
      if (alertEl) {
        alertEl.className = 'p-2.5 rounded-xl text-[11px] font-medium bg-rose-900/40 text-rose-200 border border-rose-500/30';
        alertEl.textContent = data.detail || 'Eşleştirme başarısız oldu.';
      }
    }
  } catch (err) {
    console.error('Error direct pairing:', err);
    if (alertEl) {
      alertEl.className = 'p-2.5 rounded-xl text-[11px] font-medium bg-rose-900/40 text-rose-200 border border-rose-500/30';
      alertEl.textContent = 'Sunucuyla iletişim kurulamadı.';
    }
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

async function handleTelegramTokenSubmit(event) {
  event.preventDefault();
  const inputEl = document.getElementById('bot-token-input');
  const btnEl = document.getElementById('btn-bot-token-save');
  const alertEl = document.getElementById('bot-token-alert');

  const token = inputEl ? inputEl.value.trim() : '';
  if (!token) return;

  if (btnEl) btnEl.disabled = true;
  if (alertEl) {
    alertEl.className = 'p-2 rounded-lg text-[10px] bg-blue-900/40 text-blue-200 border border-blue-500/30';
    alertEl.textContent = 'Telegram API ile doğrulanıyor ve webhook senkronize ediliyor...';
    alertEl.classList.remove('hidden');
  }

  try {
    const res = await authFetch(`${API_BASE}/bot/setup-telegram`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: token })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      if (alertEl) {
        alertEl.className = 'p-2 rounded-lg text-[10px] bg-emerald-900/40 text-emerald-200 border border-emerald-500/30';
        alertEl.textContent = data.message || 'Telegram Botu başarıyla kuruldu!';
      }
      showToast(`Telegram Botu Aktif: @${data.bot_username}`, '🤖');
      loadBotStatus();
    } else {
      if (alertEl) {
        alertEl.className = 'p-2 rounded-lg text-[10px] bg-rose-900/40 text-rose-200 border border-rose-500/30';
        alertEl.textContent = data.detail || 'Bot Token geçersiz.';
      }
    }
  } catch (err) {
    console.error('Error saving telegram token:', err);
    if (alertEl) {
      alertEl.className = 'p-2 rounded-lg text-[10px] bg-rose-900/40 text-rose-200 border border-rose-500/30';
      alertEl.textContent = 'Bağlantı hatası oluştu.';
    }
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

async function deleteUserPairing(pairingId) {
  try {
    const res = await authFetch(`${API_BASE}/bot/pairings/${pairingId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Bot bağlantısı kaldırıldı.', '🗑️');
      loadBotPairings();
    }
  } catch (err) {
    console.error('Error deleting pairing:', err);
  }
}

async function handleBotSimulatorSubmit(event) {
  event.preventDefault();
  const inputEl = document.getElementById('bot-sim-input');
  const btnEl = document.getElementById('btn-bot-sim-submit');
  const respBox = document.getElementById('bot-sim-response-box');
  const respText = document.getElementById('bot-sim-response-text');

  const text = inputEl ? inputEl.value.trim() : '';
  if (!text) return;

  if (btnEl) btnEl.disabled = true;
  if (respBox) respBox.classList.remove('hidden');
  if (respText) respText.textContent = 'İşlem çözümleniyor ve bütçeye işleniyor...';

  try {
    const res = await fetch(`${API_BASE}/bot/webhook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Bot-Token': authToken || ''
      },
      body: JSON.stringify({
        platform: 'generic',
        sender_id: 'web_simulator_user',
        message: text,
        token: authToken || ''
      })
    });

    const data = await res.json();
    if (respText) {
      respText.textContent = data.reply || data.text || 'Bot yanıtı alındı.';
    }

    if (data.success) {
      if (inputEl) inputEl.value = '';
      showToast('Bot harcamayı başarıyla kaydetti!', '✅');
      // Refresh user overview and financial data live
      if (typeof refreshAllData === 'function') {
        refreshAllData();
      }
    }
  } catch (err) {
    console.error('Error submitting bot simulation:', err);
    if (respText) {
      respText.textContent = 'Hata: Webhook ile iletişim kurulamadı.';
    }
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}




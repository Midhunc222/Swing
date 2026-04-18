document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();

    // Elements
    const navScreener = document.getElementById('nav-screener');
    const navBacktester = document.getElementById('nav-backtester');
    const secScreener = document.getElementById('screener-section');
    const secBacktester = document.getElementById('backtester-section');

    const btnRefresh = document.getElementById('refresh-screener');
    const scrStatus = document.getElementById('screener-status');
    const scrCards = document.getElementById('breakout-cards');
    const scrTimeframe = document.getElementById('screener-timeframe');

    const selTicker = document.getElementById('backtester-ticker');
    const dlTickers = document.getElementById('tickers-list');
    const selTimeframe = document.getElementById('backtester-timeframe');
    const btnRunTest = document.getElementById('run-backtest');
    const testStatus = document.getElementById('backtester-status');
    const divResults = document.getElementById('backtest-results');
    const divTrades = document.getElementById('trades-container');
    const tbodyTrades = document.getElementById('trades-tbody');

    // Stats
    const statWinRate = document.getElementById('stat-win-rate');
    const statTotal = document.getElementById('stat-total-trades');
    const statWins = document.getElementById('stat-wins');
    const statLosses = document.getElementById('stat-losses');

    // Navigation
    navScreener.addEventListener('click', () => {
        navScreener.classList.add('active');
        navBacktester.classList.remove('active');
        secScreener.classList.add('active');
        secBacktester.classList.remove('active');
    });

    navBacktester.addEventListener('click', () => {
        navBacktester.classList.add('active');
        navScreener.classList.remove('active');
        secBacktester.classList.add('active');
        secScreener.classList.remove('active');
        // Load tickers if not loaded
        if (dlTickers.children.length === 0) {
            loadTickers();
        }
    });

    async function loadTickers() {
        try {
            const res = await fetch('/api/tickers');
            const data = await res.json();
            data.tickers.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t;
                dlTickers.appendChild(opt);
            });
        } catch(e) {
            console.error('Failed to load tickers', e);
        }
    }

    // ─── Fundamentals Panel ───────────────────────────────────────────────
    const fundPanel  = document.getElementById('fundamentals-panel');
    const fundName   = document.getElementById('fund-name');
    const fundMeta   = document.getElementById('fund-meta');
    const fundDesc   = document.getElementById('fund-desc');
    const fundLtBadge    = document.getElementById('fund-lt-badge');
    const fundSwingBadge = document.getElementById('fund-swing-badge');
    const fundSignalsBox = document.getElementById('fund-signals-box');
    const fundMgmtBox    = document.getElementById('fund-mgmt-box');

    function setFmVal(id, val, suffix = '', colorFn = null) {
        const el = document.getElementById(id);
        if (!el) return;
        if (val === null || val === undefined) { el.textContent = 'N/A'; el.style.color = ''; return; }
        el.textContent = val + suffix;
        if (colorFn) el.style.color = colorFn(val);
    }

    function benchColor(val, bench, lowerIsBetter = false) {
        if (!val || !bench) return '';
        const ratio = val / bench;
        if (lowerIsBetter) {
            return ratio < 0.9 ? 'var(--success)' : ratio > 1.3 ? 'var(--danger)' : 'var(--warning)';
        }
        return ratio > 1.1 ? 'var(--success)' : ratio < 0.7 ? 'var(--danger)' : 'var(--warning)';
    }

    async function loadFundamentals(ticker) {
        fundPanel.classList.add('loading');
        fundPanel.classList.remove('hidden');
        fundName.textContent = ticker;
        fundDesc.textContent = 'Loading company data...';
        try {
            const res = await fetch(`/api/fundamentals/${encodeURIComponent(ticker)}`);
            if (!res.ok) throw new Error('Failed to load fundamentals');
            const f = await res.json();
            const b = f.sector_bench;

            fundName.textContent = f.name;
            fundMeta.textContent = `${f.sector} · ${f.industry} · Market Cap: ${f.market_cap || 'N/A'}`;
            fundDesc.textContent = f.description;

            // Verdict badges
            const ltColors = {'Attractive': 'var(--success)', 'Neutral': 'var(--warning)', 'Avoid': 'var(--danger)'};
            const swColors = {'Strong': 'var(--success)', 'Moderate': 'var(--warning)'};
            fundLtBadge.textContent  = `📈 Long Term: ${f.lt_verdict}`;
            fundLtBadge.style.background = ltColors[f.lt_verdict] || 'var(--accent)';
            fundSwingBadge.textContent = `⚡ Swing: ${f.swing_verdict}`;
            fundSwingBadge.style.background = swColors[f.swing_verdict] || 'var(--accent)';

            // Price metrics
            setFmVal('fm-mcap', f.market_cap);
            setFmVal('fm-cmp',  f.ltp,  '', v => 'var(--text-primary)');
            setFmVal('fm-52h',  f['52w_high']);
            setFmVal('fm-52l',  f['52w_low']);

            // Valuation
            setFmVal('fm-pe',     f.pe,  'x', v => v < b.pe*0.8 ? 'var(--success)' : v > b.pe*1.4 ? 'var(--danger)' : '');
            document.getElementById('fm-pe-bench').textContent = b.pe ? `Sector: ${b.pe}x` : '';
            setFmVal('fm-fpe',    f.forward_pe, 'x');
            setFmVal('fm-pb',     f.pb,  'x', v => v < b.pb*0.8 ? 'var(--success)' : v > b.pb*1.5 ? 'var(--danger)' : '');
            document.getElementById('fm-pb-bench').textContent = b.pb ? `Sector: ${b.pb}x` : '';
            setFmVal('fm-peg',    f.peg,  '', v => v < 1 ? 'var(--success)' : v > 2 ? 'var(--danger)' : '');
            setFmVal('fm-ebitda', f.ev_ebitda, 'x');

            // Profitability
            setFmVal('fm-roe',  f.roe,  '%', v => v > 18 ? 'var(--success)' : v < 8 ? 'var(--danger)' : '');
            setFmVal('fm-de',   f.debt_to_equity, '', v => v < 0.5 ? 'var(--success)' : v > 1.5 ? 'var(--danger)' : '');
            setFmVal('fm-pm',   f.profit_margin, '%');
            setFmVal('fm-rg',   f.revenue_growth, '%', v => v > 15 ? 'var(--success)' : v < 0 ? 'var(--danger)' : '');
            setFmVal('fm-eg',   f.earnings_growth, '%', v => v > 20 ? 'var(--success)' : v < 0 ? 'var(--danger)' : '');
            setFmVal('fm-div',  f.dividend_yield, '%');
            setFmVal('fm-promo', f.promoter_holding, '%', v => v > 50 ? 'var(--success)' : v < 25 ? 'var(--warning)' : '');

            // Signals & Cautions
            let sigHtml = '<h4>📊 Fundamental Signals</h4>';
            f.signals.forEach(s => { sigHtml += `<div class="fund-signal green">✅ ${s}</div>`; });
            f.cautions.forEach(c => { sigHtml += `<div class="fund-signal red">⚠️ ${c}</div>`; });
            if (!f.signals.length && !f.cautions.length) sigHtml += '<div class="fund-signal">No strong signals detected.</div>';
            fundSignalsBox.innerHTML = sigHtml;

            // Management
            let mgmtHtml = '<h4>👤 Key Management</h4>';
            if (f.management.length) {
                f.management.forEach(m => { mgmtHtml += `<div class="mgmt-row"><b>${m.name}</b><span>${m.title}</span></div>`; });
            } else {
                mgmtHtml += '<div>Details unavailable.</div>';
            }
            fundMgmtBox.innerHTML = mgmtHtml;

        } catch(e) {
            fundDesc.textContent = 'Could not load company data: ' + e.message;
        } finally {
            fundPanel.classList.remove('loading');
        }
    }

    // Auto-fetch fundamentals when ticker is typed/selected
    let fundDebounce = null;
    selTicker.addEventListener('input', () => {
        clearTimeout(fundDebounce);
        const t = selTicker.value.trim();
        if (t.length > 3) {
            fundDebounce = setTimeout(() => loadFundamentals(t), 600);
        } else {
            fundPanel.classList.add('hidden');
        }
    });

    // Screener
    async function scanMarket(forceRefresh = false) {
        const interval = scrTimeframe.value;
        const icon = btnRefresh.querySelector('svg') || btnRefresh.querySelector('i');
        if (icon) icon.classList.add('spin');
        btnRefresh.disabled = true;
        let tfText = 'Daily';
        if (interval === '1wk') tfText = 'Weekly';
        if (interval === '1mo') tfText = 'Monthly';
        scrStatus.textContent = `Scanning Nifty 500 for ${tfText} historical setups... This takes ~1-3 minutes.`;
        scrCards.innerHTML = '';

        try {
            const res = await fetch(`/api/screener?interval=${interval}&force=${forceRefresh}`);
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Server Error (${res.status})`);
            }
            const data = await res.json();
            
            const m = data.metrics;
            const pctText = interval === '1d' ? '12%' : '25%';
            if (data.breakouts.length === 0) {
                scrStatus.innerHTML = `Scanned ${m.successfully_scanned} / ${m.total_universe} stocks successfully (${m.failed_tickers} failed data fetch). <br/> No active High/Med Conviction signals found <b>within ${pctText} of Supertrend</b> on ${interval} timeframe.`;
            } else {
                scrStatus.innerHTML = `Found <b style="color:var(--success)">${data.breakouts.length}</b> early-catch candidates! <br/> <small>Scanned ${m.successfully_scanned} stocks. Filtered strictly for CMP within ${pctText} of Supertrend.</small>`;
                data.breakouts.forEach(b => {
                    const card = document.createElement('div');
                    card.className = 'breakout-card';
                    card.style.cursor = 'pointer';
                    card.title = 'Click to run backtest details';
                    card.innerHTML = `
                        <div class="card-header">
                            <span class="ticker-symbol">${b.ticker}</span>
                            <span class="badge badge-${b.conviction.toLowerCase()}">${b.conviction} Conviction</span>
                        </div>
                        <p class="card-reason">${b.reason}</p>
                        
                        <div class="stats-grid">
                            <div class="stat-box">
                                <span class="label">CMP (Entry)</span>
                                <span class="value">₹${b.close}</span>
                            </div>
                            <div class="stat-box">
                                <span class="label">Stop Loss</span>
                                <span class="value" style="color:var(--danger)">₹${b.sl}</span>
                            </div>
                            <div class="stat-box">
                                <span class="label">Target (1:2 R:R)</span>
                                <span class="value" style="color:var(--success)">₹${b.target}</span>
                            </div>
                            <div class="stat-box">
                                <span class="label">Hold Time</span>
                                <span class="value">${b.duration}</span>
                            </div>
                            <div class="stat-box">
                                <span class="label">Historical Win Rate</span>
                                <span class="value ${b.win_rate > 50 ? 'text-accent' : ''}">${b.win_rate}%</span>
                            </div>
                            <div class="stat-box">
                                <span class="label">RSI</span>
                                <span class="value">${b.rsi}</span>
                            </div>
                            <div class="stat-box">
                                <span class="label">Vol vs Avg</span>
                                <span class="value" style="color:${b.vol_ratio >= 2 ? 'var(--success)' : b.vol_ratio >= 1.5 ? '#f59e0b' : 'var(--text-secondary)'}">${b.vol_ratio}x 📊</span>
                            </div>
                        </div>
                        
                        <div class="ema-footer">
                            <span>EMA 50: <b>${b.ema_50}</b></span>
                            <span>EMA 200: <b>${b.ema_200}</b></span>
                            <span>Supertrend: <b>${b.supertrend}</b></span>
                        </div>
                    `;
                    
                    card.addEventListener('click', () => {
                        // Switch view
                        navBacktester.click();
                        
                        setTimeout(() => {
                            // Ensure the option is natively populated in the datalist 
                            let exists = false;
                            for(let i=0; i<dlTickers.children.length; i++){
                                if(dlTickers.children[i].value === b.ticker) exists = true;
                            }
                            if (!exists) {
                                const opt = document.createElement('option');
                                opt.value = b.ticker;
                                dlTickers.appendChild(opt);
                            }
                            
                            selTicker.value = b.ticker;
                            selTimeframe.value = interval; // Match the timeframe it was screened on
                            
                            // Execute test automatically
                            btnRunTest.click();
                        }, 50);
                    });
                    
                    scrCards.appendChild(card);
                });
                lucide.createIcons(); // refresh icons on new cards
            }
        } catch(e) {
            scrStatus.textContent = `Error scanning market: ${e.message}`;
        } finally {
            const icon = btnRefresh.querySelector('svg') || btnRefresh.querySelector('i');
            if (icon) icon.classList.remove('spin');
            btnRefresh.disabled = false;
        }
    }
    
    // Listeners
    btnRefresh.addEventListener('click', () => scanMarket(true));

    // Initial Load
    scanMarket(false);

    // Backtester
    btnRunTest.addEventListener('click', async () => {
        const t = selTicker.value;
        if (!t) {
            alert('Please select a ticker');
            return;
        }
        const interval = selTimeframe.value;
        
        btnRunTest.disabled = true;
        const icon = btnRunTest.querySelector('svg') || btnRunTest.querySelector('i');
        if (icon) {
            icon.classList.add('spin');
        }
        testStatus.textContent = `Running ${interval} backtest for ${t}...`;
        divResults.classList.add('hidden');
        divTrades.classList.add('hidden');
        tbodyTrades.innerHTML = '';

        try {
            const res = await fetch(`/api/backtest`, {
                method: 'POST',
                headers:{ 'Content-Type': 'application/json'},
                body: JSON.stringify({ ticker: t, interval: interval })
            });

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.detail || 'Test Failed');
            }

            const data = await res.json();
            const results = data.results;

            let durText = '60 Days';
            if (interval === '1wk') durText = '12 Weeks';
            if (interval === '1mo') durText = '3 Months';
            testStatus.innerHTML = `Backtest complete for ${t} (${interval})! <br/> <small style="color:var(--text-secondary)">*Time Stop Enforced: Trades forced closed if held > ${durText}.</small>`;
            
            // Pop Stats
            statWinRate.textContent = `${results.win_rate}%`;
            statTotal.textContent = results.total_trades;
            statWins.textContent = results.wins;
            statLosses.textContent = results.losses;

            // Load Table
            if (results.trades.length > 0) {
                results.trades.forEach(tr => {
                    const row = document.createElement('tr');
                    const isWin = tr.profit_percent > 0;
                    row.innerHTML = `
                        <td>${tr.entry_date}</td>
                        <td>${tr.exit_date}</td>
                        <td>₹${tr.entry_price}</td>
                        <td>₹${tr.exit_price}</td>
                        <td class="${isWin ? 'profit-positive' : 'profit-negative'}">
                            ${isWin ? '+' : ''}${tr.profit_percent}%
                        </td>
                    `;
                    tbodyTrades.appendChild(row);
                });
            } else {
                 const row = document.createElement('tr');
                 row.innerHTML = `<td colspan="5" style="text-align:center">No trades taken in this period.</td>`;
                 tbodyTrades.appendChild(row);
            }

            divResults.classList.remove('hidden');
            divTrades.classList.remove('hidden');
        } catch(e) {
            testStatus.textContent = `Error running backtest: ${e.message}`;
        } finally {
            const icon = btnRunTest.querySelector('svg') || btnRunTest.querySelector('i');
            if (icon) {
                icon.classList.remove('spin');
            }
            btnRunTest.disabled = false;
        }
    });
});

// Copyright (C) 2025-2026 Yusuf Mert Turan
// SPDX-License-Identifier: AGPL-3.0-or-later
// J Mod Downloader: injects "+ Add" / "✓ In list" pills into Steam Workshop pages.
// Runs in an isolated JS world (the page's own scripts can't reach the bridge).
// Steam markup changes break things here first: every selector lives in SELECTORS.
(function(){
    if(window.__jmdInjected){
        return;
    }
    window.__jmdInjected = true;

    const SELECTORS = {
        itemLink: 'a[href*="filedetails/?id="]',
        detailSubscribe: '#SubscribeItemBtn',
        requiredItems: '#RequiredItems a[href*="filedetails/?id="]',
        collectionChildren: '.collectionChildren',
        collectionSubscribe: '.subscribeCollection',
        collectionItem: '.collectionItem',
        collectionItemControls: '.subscriptionControls',
    };
    const MIN_TILE_WIDTH = 80;
    const ACCENT = '#f0609e';

    let bridge = null;
    let queued = new Set();

    // === STYLE ===
    const css = `
.jmd-pill{display:inline-flex;align-items:center;gap:4px;height:22px;padding:0 9px;box-sizing:border-box;
  background:${ACCENT};border:1px solid ${ACCENT};border-radius:11px;color:#1a0d14;cursor:pointer;
  font:700 11px/1 Inter,"Segoe UI",Roboto,sans-serif;white-space:nowrap;user-select:none;text-decoration:none}
.jmd-pill:hover{background:#f57db1;border-color:#f57db1}
.jmd-pill:active{background:#d64c88;border-color:#d64c88}
.jmd-pill.jmd-in{background:#2b1c26;border-color:#6d3558;color:#f59cc3}
.jmd-pill.jmd-in:hover{background:#3a2331;border-color:#8a4470}
.jmd-pill.jmd-lg{height:30px;padding:0 14px;border-radius:15px;font-size:12px;gap:6px;vertical-align:middle}
.jmd-pill svg{flex:none}
.jmd-tile-host{position:relative !important}
.jmd-tile-pill{position:absolute;top:6px;right:6px;z-index:5}
.jmd-tag{display:inline-flex;align-items:center;height:18px;margin-left:6px;padding:0 7px;border:1px solid #6d3558;
  border-radius:9px;color:#f59cc3;font:600 10.5px/1 Inter,"Segoe UI",Roboto,sans-serif;vertical-align:middle}
.jmd-row-pill{margin-right:8px;vertical-align:middle}
`;
    const PLUS = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>';
    const CHECK = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';

    function addStyle(){
        if(document.getElementById('jmd-style')){
            return;
        }
        const el = document.createElement('style');
        el.id = 'jmd-style';
        el.textContent = css;
        (document.head || document.documentElement).appendChild(el);
    }

    function idFromHref(href){
        const m = /[?&]id=(\d+)/.exec(href || '');
        return m ? m[1] : null;
    }

    // === PILLS ===
    function makePill(id, kind, label){
        const pill = document.createElement('span');
        pill.className = 'jmd-pill' + (kind === 'lg' ? ' jmd-lg' : '');
        pill.dataset.jmdId = id;
        pill.dataset.jmdLabel = label;
        pill.setAttribute('role', 'button');
        pill.addEventListener('click', function(ev){
            ev.preventDefault();
            ev.stopPropagation();
            if(!bridge){
                return;
            }
            if(queued.has(id)){
                bridge.remove(id);
            }else{
                bridge.add(id);
            }
        }, true);
        paint(pill);
        return pill;
    }

    function paint(pill){
        const id = pill.dataset.jmdId;
        const inList = queued.has(id);
        const lg = pill.classList.contains('jmd-lg');
        pill.classList.toggle('jmd-in', inList);
        const text = inList ? (pill.dataset.jmdLabel === 'collection' ? 'Collection in list' : 'In list')
                            : (pill.dataset.jmdLabel === 'collection' ? addCollectionLabel() : (lg ? 'Add to list' : 'Add'));
        const icon = inList ? CHECK : PLUS;
        pill.innerHTML = lg ? icon.replace(/"11"/g, '"13"') + text : icon + text;
        pill.title = inList ? 'In your list. Click to remove.' : 'Add to J Mod Downloader';
    }

    function addCollectionLabel(){
        const n = document.querySelectorAll(SELECTORS.collectionItem).length;
        return n ? 'Add collection (' + n + ')' : 'Add collection';
    }

    function repaintAll(){
        document.querySelectorAll('.jmd-pill').forEach(paint);
    }

    // === PAGE TYPES ===
    function pageId(){
        return idFromHref(location.href);
    }

    function injectDetail(){
        const btn = document.querySelector(SELECTORS.detailSubscribe);
        const id = pageId();
        if(!btn || !id || btn.parentElement.querySelector('.jmd-pill')){
            return;
        }
        const pill = makePill(id, 'lg', 'item');
        pill.style.marginLeft = '8px';
        btn.insertAdjacentElement('afterend', pill);
        document.querySelectorAll(SELECTORS.requiredItems).forEach(function(a){
            if(a.querySelector('.jmd-tag')){
                return;
            }
            const tag = document.createElement('span');
            tag.className = 'jmd-tag';
            tag.textContent = 'Will be added automatically';
            (a.firstElementChild || a).appendChild(tag);
        });
    }

    function injectCollection(){
        const host = document.querySelector(SELECTORS.collectionSubscribe);
        const id = pageId();
        if(host && id && !document.querySelector('.jmd-coll-row')){
            // own row: Steam's collection buttons are tightly packed and wrap if we squeeze in
            const row = document.createElement('div');
            row.className = 'jmd-coll-row';
            row.style.margin = '8px 0';
            row.appendChild(makePill(id, 'lg', 'collection'));
            host.insertAdjacentElement('afterend', row);
        }
        document.querySelectorAll(SELECTORS.collectionItem).forEach(function(row){
            const itemId = (row.id || '').replace('sharedfile_', '');
            const controls = row.querySelector(SELECTORS.collectionItemControls);
            if(!itemId || !controls || controls.querySelector('.jmd-pill')){
                return;
            }
            const pill = makePill(itemId, 'sm', 'item');
            pill.classList.add('jmd-row-pill');
            controls.insertBefore(pill, controls.firstChild);
        });
    }

    function injectTiles(){
        document.querySelectorAll(SELECTORS.itemLink).forEach(function(a){
            if(a.dataset.jmdDone || !a.querySelector('img')){
                return;
            }
            if(a.closest(SELECTORS.collectionItem) || a.closest('.jmd-pill')){
                return;
            }
            const id = idFromHref(a.getAttribute('href'));
            if(!id || id === pageId()){
                return;
            }
            const rect = a.getBoundingClientRect();
            if(rect.width && rect.width < MIN_TILE_WIDTH){
                return;
            }
            a.dataset.jmdDone = '1';
            const host = a.parentElement || a;
            if(host.querySelector(':scope > .jmd-tile-pill')){
                return;
            }
            host.classList.add('jmd-tile-host');
            const pill = makePill(id, 'sm', 'item');
            pill.classList.add('jmd-tile-pill');
            host.appendChild(pill);
        });
    }

    function scan(){
        addStyle();
        if(pageId() && document.querySelector(SELECTORS.collectionChildren)){
            injectCollection();
        }else if(pageId()){
            injectDetail();
        }
        injectTiles();
    }

    // === WIRING ===
    let pending = null;
    function scheduleScan(){
        if(pending){
            return;
        }
        pending = setTimeout(function(){
            pending = null;
            scan();
        }, 150);
    }

    function setQueued(ids){
        queued = new Set(ids);
        repaintAll();
    }

    function connect(){
        if(typeof QWebChannel === 'undefined' || typeof qt === 'undefined'){
            setTimeout(connect, 100);
            return;
        }
        new QWebChannel(qt.webChannelTransport, function(channel){
            bridge = channel.objects.jmd;
            bridge.queuedChanged.connect(setQueued);
            bridge.snapshot(setQueued);
            scan();
        });
    }

    new MutationObserver(scheduleScan).observe(document.documentElement, {childList: true, subtree: true});
    scan();
    connect();
})();

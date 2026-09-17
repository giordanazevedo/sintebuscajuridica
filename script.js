const searchInput = document.getElementById('search-input');
        const clearBtn = document.getElementById('clear-btn');
        const syncBtn = document.getElementById('sync-btn');
        const resultsHeader = document.getElementById('results-header');
        const resultsCount = document.getElementById('results-count');
        const resultsContent = document.getElementById('results-content');
        const toastContainer = document.getElementById('toast-container');

        // Mapa de planilhas para permitir links clicáveis nas buscas
        const mapaPlanilhasUrls = {};

        async function inicializarMapaPlanilhas() {
            const senhaSalva = sessionStorage.getItem('sinte_senha_planilhas');
            if (!senhaSalva) return;
            try {
                const response = await fetch('/api/planilhas', {
                    headers: { 'Authorization': senhaSalva }
                });
                const data = await response.json();
                if (data.success) {
                    data.planilhas.forEach(p => {
                        mapaPlanilhasUrls[p.nome.toUpperCase().trim()] = p.url;
                        if (p.url.startsWith('/planilhas/')) {
                            const filename = p.url.replace('/planilhas/', '');
                            mapaPlanilhasUrls[filename.toUpperCase().trim()] = p.url;
                            mapaPlanilhasUrls[filename.replace('.xlsx', '').replace('.xls', '').toUpperCase().trim()] = p.url;
                        }
                    });
                }
            } catch (e) {
                console.error("Erro ao inicializar mapa de planilhas:", e);
            }
        }

        inicializarMapaPlanilhas();

        // Modal Controls
        const btnOpenPlanilhas = document.getElementById('btn-open-planilhas');
        const btnCloseModal = document.getElementById('btn-close-modal');
        const btnCloseModalX = document.getElementById('btn-close-modal-x');
        const modalPlanilhas = document.getElementById('modal-planilhas');
        const planilhasGrid = document.getElementById('planilhas-grid');
        const modalSearchInput = document.getElementById('modal-search-input');

        let debounceTimeout;

        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = 'toast ' + type;

            let icon = '';
            if (type === 'success') {
                icon = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="3" style="width:20px;height:20px;"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            } else if (type === 'error') {
                icon = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="3" style="width:20px;height:20px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
            }

            toast.innerHTML = icon + '<span class="toast-message">' + message + '</span>';

            toastContainer.appendChild(toast);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                toast.style.transition = 'all 0.5s ease-in-out';
                setTimeout(() => toast.remove(), 500);
            }, 4000);
        }

        function formatCPF(cpf) {
            if (!cpf || cpf === 'Não informado' || cpf === 'NAN' || cpf === '0' || cpf === '-') return 'Não informado';
            let cleaned = String(cpf).replace(/\D/g, '');
            if (!cleaned || /^0+$/.test(cleaned)) return 'Não informado';
            if (cleaned.length <= 11) {
                cleaned = cleaned.padStart(11, '0');
                return cleaned.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
            }
            return cpf;
        }

        function formatMatricula(mat) {
            if (!mat || mat === 'Não informada' || mat === 'NAN' || mat === '0' || mat === '-') return 'Não informada';
            return mat;
        }

        searchInput.addEventListener('input', () => {
            const query = searchInput.value;

            if (query.trim().length > 0) {
                clearBtn.style.display = 'flex';
            } else {
                clearBtn.style.display = 'none';
            }

            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(() => {
                performSearch(query);
            }, 250);
        });



        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            clearBtn.style.display = 'none';
            performSearch('');
            searchInput.focus();
        });

        async function performSearch(query) {
            const trimmed = query.trim();

            if (trimmed.length < 2) {
                resultsHeader.style.display = 'none';
                resultsContent.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg><h3>Sistema Pronto para Consulta</h3><p>Digite pelo menos 2 caracteres do CPF, Matrícula ou Nome do professor/servidor acima para pesquisar.</p></div>';
                return;
            }

            resultsContent.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" style="animation: spin 1.5s linear infinite;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><h3 style="color:var(--accent);">Pesquisando...</h3><p>Buscando na base de dados unificada...</p></div>';

            try {
                const response = await fetch('/api/search?q=' + encodeURIComponent(trimmed));
                const data = await response.json();

                renderResults(data.results, trimmed);
            } catch (error) {
                console.error("Erro na busca:", error);
                showToast("Erro ao conectar com o servidor.", "error");
                resultsContent.innerHTML = '<div class="empty-state" style="border-color: var(--danger);"><svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><h3 style="color: var(--danger)">Erro na Pesquisa</h3><p>Não foi possível buscar as informações. Certifique-se de que o servidor local está rodando.</p></div>';
            }
        }

        function renderResults(results, searchTerm) {
            resultsHeader.style.display = 'flex';

            if (!results || results.length === 0) {
                resultsCount.innerHTML = 'Nenhum registro correspondente a "<span>' + escapeHTML(searchTerm) + '</span>"';
                resultsContent.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="15.01" y2="9"></line><line x1="9" y1="9" x2="9.01" y2="9"></line><path d="M16 16s-1.5-2-4-2-4 2-4 2"></path></svg><h3>Nenhum registro encontrado</h3><p>Nenhum servidor foi localizado com este termo. Verifique a digitação.</p></div>';
                return;
            }

            const grouped = {};
            results.forEach(item => {
                const nameKey = (item.nome || 'SEM NOME').toUpperCase().trim();
                if (!grouped[nameKey]) {
                    grouped[nameKey] = {
                        nome: item.nome || 'SEM NOME',
                        links: []
                    };
                }
                grouped[nameKey].links.push(item);
            });

            const uniqueNamesCount = Object.keys(grouped).length;
            resultsCount.innerHTML = 'Encontrado(s) <span>' + uniqueNamesCount + '</span> servidor(es) com total de <span>' + results.length + '</span> vínculos/ações';

            let html = '<div class="cards-list">';

            for (const key in grouped) {
                const server = grouped[key];
                const occurrenceText = server.links.length === 1 ? '1 ocorrência' : server.links.length + ' ocorrências / vínculos';

                // Verifica se há vínculo de herdeiros em algum dos registros do servidor
                let herdeiroInfoGeral = null;
                for (const l of server.links) {
                    if (l.herdeiro_info) {
                        herdeiroInfoGeral = l.herdeiro_info;
                        break;
                    }
                }

                let badgeHerdeiroHtml = '';
                if (herdeiroInfoGeral) {
                    const cxTxt = herdeiroInfoGeral.caixa ? ' • Arquivado na ' + escapeHTML(herdeiroInfoGeral.caixa) : ' • Em andamento no Jurídico';
                    badgeHerdeiroHtml = `
                        <div class="herdeiro-card-badge" onclick="irParaHerdeiro('${escapeHTML(herdeiroInfoGeral.id)}')" title="Clique para abrir o processo de herdeiros deste titular">
                            <div style="display:flex; align-items:center; gap:0.65rem;">
                                <span class="herdeiro-badge-icon">⚖️</span>
                                <div>
                                    <strong style="color:var(--primary); font-size:0.88rem;">Processo de Herdeiros Cadastrado (${escapeHTML(herdeiroInfoGeral.status_label)})</strong>
                                    <span style="display:block; font-size:0.75rem; color:var(--text-muted);">${escapeHTML(herdeiroInfoGeral.id)}${cxTxt}</span>
                                </div>
                            </div>
                            <button type="button" class="btn-goto-herdeiro" onclick="event.stopPropagation(); irParaHerdeiro('${escapeHTML(herdeiroInfoGeral.id)}')">Ver Ficha &raquo;</button>
                        </div>
                    `;
                }

                html += '<div class="server-card"><div class="card-header"><div class="server-name-container"><h3 class="server-name">' + escapeHTML(server.nome) + '</h3></div><span class="occurrence-badge">' + occurrenceText + '</span></div><div class="card-body">' + badgeHerdeiroHtml;

                server.links.forEach(link => {
                    const detalheExibir = link.info || link.detalhes || 'Nenhum detalhe adicional informado.';
                    const nomeArquivo = (link.arquivo || '').replace('.xlsx', '').replace('Local: ', '');
                    const nomeArquivoEscaped = escapeHTML(nomeArquivo);
                    const tagAbaHtml = link.aba ? '<span class="source-tag aba-tag">' + escapeHTML(link.aba) + '</span>' : '';
                    const tagRegionalHtml = link.regional ? '<span class="source-tag" style="background:#f0fdf4; border-color:#bbf7d0; color:#16a34a;"><svg viewBox="0 0 24 24" style="fill:none; stroke:currentColor; stroke-width:2; width:12px; height:12px; margin-right:2px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>' + escapeHTML(link.regional) + '</span>' : '';

                    html += '<div class="link-item"><div class="meta-field"><span class="meta-label">Matrícula</span><span class="meta-value highlight">' + escapeHTML(formatMatricula(link.matricula)) + '</span></div><div class="meta-field"><span class="meta-label">CPF</span><span class="meta-value highlight">' + escapeHTML(formatCPF(link.cpf)) + '</span></div><div class="meta-field"><span class="meta-label">Ação / Origem Jurídica</span><div class="meta-value" style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-top:0.25rem;"><button type="button" class="source-tag acao-tag clickable-tag" data-acao="' + nomeArquivoEscaped + '" title="Clique para abrir a planilha desta ação"><svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg><span>' + nomeArquivoEscaped + '</span></button>' + tagAbaHtml + tagRegionalHtml + '</div></div><div class="meta-field" style="grid-column: 1 / -1;"><span class="meta-label">Detalhes da Planilha</span><span class="meta-value info-tag">' + escapeHTML(detalheExibir) + '</span></div></div>';
                });

                html += '</div></div>';
            }

            html += '</div>';
            resultsContent.innerHTML = html;
        }

        function escapeHTML(str) {
            if (!str) return '';
            return str
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        // --- CONTROLE DE STATUS DA SINCRONIZAÇÃO AUTOMÁTICA ---
        const syncStatusContainer = document.getElementById('sync-status-container');
        const syncStatusText = document.getElementById('sync-status-text');
        const syncStatusDot = document.getElementById('sync-status-dot');

        async function atualizarStatusSincronizacao() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                if (data.success) {
                    if (data.sincronizando) {
                        if (syncStatusText) syncStatusText.textContent = 'Auto-Sync: Atualizando...';
                        if (syncStatusDot) syncStatusDot.className = 'sync-status-dot syncing';
                        if (!syncBtn.classList.contains('loading')) {
                            syncBtn.classList.add('loading');
                            syncBtn.querySelector('span').textContent = 'Sincronizando...';
                        }
                    } else {
                        // Not syncing. Se estava sincronizando, avisa que terminou
                        if (syncBtn.classList.contains('loading')) {
                            syncBtn.classList.remove('loading');
                            syncBtn.querySelector('span').textContent = 'Sincronizar Dados';
                            showToast('Sincronização concluída com sucesso!', 'success');
                            if (searchInput.value.trim().length >= 2) {
                                performSearch(searchInput.value);
                            }
                        }

                        if (data.ultima_sincronizacao) {
                            const horaMatch = data.ultima_sincronizacao.match(/(\d{2}:\d{2})/);
                            const horaFormatada = horaMatch ? horaMatch[1] : data.ultima_sincronizacao;
                            if (syncStatusText) syncStatusText.textContent = `Auto-Sync ativo • ${horaFormatada}`;
                            if (syncStatusDot) syncStatusDot.className = 'sync-status-dot';
                            if (syncStatusContainer) syncStatusContainer.title = `Última sincronização: ${data.ultima_sincronizacao} (${data.total_registros.toLocaleString()} registros). Atualiza automaticamente a cada ${data.intervalo_minutos} min.`;
                        }
                    }
                }
            } catch (e) {
                console.warn("Status de sync indisponível:", e);
            }
        }

        atualizarStatusSincronizacao();
        // Aumenta a frequência do polling para 5 segundos se estiver atualizando
        setInterval(() => {
            if (syncBtn.classList.contains('loading')) {
                atualizarStatusSincronizacao();
            }
        }, 5000);
        setInterval(atualizarStatusSincronizacao, 30000);

        syncBtn.addEventListener('click', async () => {
            if (syncBtn.classList.contains('loading')) return;

            syncBtn.classList.add('loading');
            syncBtn.querySelector('span').textContent = 'Sincronizando...';
            if (syncStatusText) syncStatusText.textContent = 'Sincronizando manual...';
            if (syncStatusDot) syncStatusDot.className = 'sync-status-dot syncing';

            showToast("Sincronização iniciada em segundo plano...", "success");

            try {
                const response = await fetch('/api/sync');
                const data = await response.json();

                if (!data.success) {
                    showToast('Erro ao iniciar sincronização: ' + data.error, "error");
                    syncBtn.classList.remove('loading');
                    syncBtn.querySelector('span').textContent = 'Sincronizar Dados';
                    atualizarStatusSincronizacao();
                }
                // Se sucesso, a verificação de término fica a cargo do atualizarStatusSincronizacao via polling
            } catch (error) {
                console.error("Erro na sincronização:", error);
                showToast("Erro ao conectar ao servidor para sincronização.", "error");
                syncBtn.classList.remove('loading');
                syncBtn.querySelector('span').textContent = 'Sincronizar Dados';
                atualizarStatusSincronizacao();
            }
        });

        // --- LOGICA DE BUSCA POR REGIONAL (CIDADE) ---
        const tabServidor = document.getElementById('tab-servidor');
        const tabRegional = document.getElementById('tab-regional');
        const wrapperServidor = document.getElementById('wrapper-servidor');
        const wrapperRegional = document.getElementById('wrapper-regional');
        const tipsServidor = document.getElementById('tips-servidor');
        const tipsRegional = document.getElementById('tips-regional');

        const regionalInput = document.getElementById('regional-input');
        const clearRegionalBtn = document.getElementById('clear-regional-btn');
        const regionaisList = document.getElementById('regionais-list');

        const tabHerdeiros = document.getElementById('tab-herdeiros');
        const herdeirosSection = document.getElementById('herdeiros-section');
        const badgeHerdeirosPendentes = document.getElementById('badge-herdeiros-pendentes');
        const searchSection = document.querySelector('.search-section');
        const resultsSection = document.querySelector('.results-section');

        let modoBusca = 'servidor'; // 'servidor', 'regional' ou 'herdeiros'
        let listaCidades = [];

        // Alterna entre abas
        tabServidor.addEventListener('click', () => {
            if (modoBusca === 'servidor') return;
            modoBusca = 'servidor';

            tabServidor.classList.add('active');
            tabRegional.classList.remove('active');
            if (tabHerdeiros) tabHerdeiros.classList.remove('active');

            if (herdeirosSection) herdeirosSection.style.display = 'none';
            if (searchSection) searchSection.style.display = '';
            if (resultsSection) resultsSection.style.display = '';

            wrapperServidor.style.display = 'flex';
            wrapperRegional.style.display = 'none';
            tipsServidor.style.display = 'flex';
            tipsRegional.style.display = 'none';
            resultsContent.style.display = '';
            resultsHeader.style.display = 'none';

            // Restaura estado anterior de busca
            performSearch(searchInput.value);
            searchInput.focus();
        });

        tabRegional.addEventListener('click', async () => {
            if (modoBusca === 'regional') return;
            modoBusca = 'regional';

            tabRegional.classList.add('active');
            tabServidor.classList.remove('active');
            if (tabHerdeiros) tabHerdeiros.classList.remove('active');

            if (herdeirosSection) herdeirosSection.style.display = 'none';
            if (searchSection) searchSection.style.display = '';
            if (resultsSection) resultsSection.style.display = '';

            wrapperRegional.style.display = 'flex';
            wrapperServidor.style.display = 'none';
            tipsRegional.style.display = 'flex';
            tipsServidor.style.display = 'none';
            resultsContent.style.display = '';

            // Carrega a lista de regionais se ainda não foi carregada
            if (listaCidades.length === 0) {
                await carregarListaRegionais();
            }

            performSearchRegional(regionalInput.value);
            regionalInput.focus();
        });

        if (tabHerdeiros) {
            tabHerdeiros.addEventListener('click', () => {
                if (modoBusca === 'herdeiros') return;
                modoBusca = 'herdeiros';

                tabHerdeiros.classList.add('active');
                tabServidor.classList.remove('active');
                tabRegional.classList.remove('active');

                if (searchSection) searchSection.style.display = 'none';
                if (resultsSection) resultsSection.style.display = 'none';
                if (herdeirosSection) herdeirosSection.style.display = 'flex';

                carregarHerdeiros();
                carregarCaixasFiltro();
            });
        }



        // Carrega a lista de regionais do backend
        async function carregarListaRegionais() {
            try {
                const res = await fetch('/api/regionais');
                const data = await res.json();
                if (data.success) {
                    listaCidades = data.regionais;
                    regionaisList.innerHTML = listaCidades.map(c => `<option value="${escapeHTML(c)}"></option>`).join('');
                }
            } catch (e) {
                console.error("Erro ao carregar lista de regionais:", e);
            }
        }

        // Listener de input para busca por regional
        regionalInput.addEventListener('input', () => {
            const query = regionalInput.value;
            if (query.trim().length > 0) {
                clearRegionalBtn.style.display = 'flex';
            } else {
                clearRegionalBtn.style.display = 'none';
            }

            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(() => {
                performSearchRegional(query);
            }, 300);
        });

        clearRegionalBtn.addEventListener('click', () => {
            regionalInput.value = '';
            clearRegionalBtn.style.display = 'none';
            performSearchRegional('');
            regionalInput.focus();
        });

        async function performSearchRegional(query) {
            const trimmed = query.trim().toUpperCase();

            if (trimmed.length < 2) {
                resultsHeader.style.display = 'none';
                resultsContent.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg><h3>Busca por Regional</h3><p>Selecione ou digite o nome de uma cidade/regional acima para consultar estatísticas e visualizar os servidores cadastrados.</p></div>';
                return;
            }

            // Exibe carregamento
            resultsContent.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" style="animation: spin 1.5s linear infinite;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg><h3 style="color:var(--accent);">Carregando Estatísticas...</h3><p>Consultando dados da regional...</p></div>';

            try {
                const response = await fetch('/api/regional/stats?q=' + encodeURIComponent(trimmed));
                const data = await response.json();

                if (data.success && data.total > 0) {
                    renderRegionalResults(data);
                } else {
                    resultsHeader.style.display = 'flex';
                    resultsCount.innerHTML = 'Nenhum registro correspondente a "<span>' + escapeHTML(trimmed) + '</span>"';
                    resultsContent.innerHTML = '<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="15.01" y2="9"></line><line x1="9" y1="9" x2="9.01" y2="9"></line><path d="M16 16s-1.5-2-4-2-4 2-4 2"></path></svg><h3>Nenhum servidor nesta regional</h3><p>Verifique o nome digitado ou selecione outra regional da lista.</p></div>';
                }
            } catch (error) {
                console.error("Erro na busca por regional:", error);
                showToast("Erro ao conectar com o servidor.", "error");
                resultsContent.innerHTML = '<div class="empty-state" style="border-color: var(--danger);"><svg viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg><h3 style="color: var(--danger)">Erro na Pesquisa</h3><p>Não foi possível carregar as estatísticas da regional.</p></div>';
            }
        }

        function renderRegionalResults(data) {
            resultsHeader.style.display = 'flex';
            resultsCount.innerHTML = 'Regional <span>' + escapeHTML(data.regional) + '</span> possui <span>' + data.total + '</span> servidores cadastrados';

            // Cria o dashboard de estatísticas
            let breakdownHtml = '';
            for (const acao in data.por_acao) {
                breakdownHtml += `
                    <div class="breakdown-item">
                        <span class="breakdown-name" title="${escapeHTML(acao)}">${escapeHTML(acao)}</span>
                        <span class="breakdown-badge">${data.por_acao[acao]}</span>
                    </div>
                `;
            }

            let html = `
                <div class="regional-dashboard">
                    <div class="regional-stats-card">
                        <div class="stats-icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                        </div>
                        <div class="stats-info">
                            <span class="stats-label">Total de Servidores</span>
                            <span class="stats-number">${data.total}</span>
                        </div>
                    </div>
                    
                    <div class="regional-breakdown-card">
                        <h4 class="breakdown-title">Distribuição por Ação / Origem Jurídica</h4>
                        <div class="breakdown-list">
                            ${breakdownHtml}
                        </div>
                    </div>
                </div>
            `;

            // Agora, renderiza a lista de servidores dessa regional usando o mesmo formato visual
            html += `
                <div id="gm-fundef-regional-block" style="margin-bottom:1.5rem;">
                    <div class="gm-loading" style="padding:1.5rem 0;">
                        <svg viewBox="0 0 24 24" fill="none"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                        <span>Calculando GM + FUNDEF para ${escapeHTML(data.regional)}...</span>
                    </div>
                </div>
            `;
            html += '<h3 style="font-family:\'Outfit\',sans-serif; color:var(--accent); margin-bottom: 1rem; text-align:left;">Lista de Servidores</h3>';

            // Agrupa os servidores da regional por nome
            const grouped = {};
            data.pessoas.forEach(item => {
                const nameKey = (item.nome || 'SEM NOME').toUpperCase().trim();
                if (!grouped[nameKey]) {
                    grouped[nameKey] = {
                        nome: item.nome || 'SEM NOME',
                        links: []
                    };
                }
                grouped[nameKey].links.push(item);
            });

            html += '<div class="cards-list">';
            for (const key in grouped) {
                const server = grouped[key];
                const occurrenceText = server.links.length === 1 ? '1 ocorrência' : server.links.length + ' ocorrências / vínculos';

                html += '<div class="server-card"><div class="card-header"><div class="server-name-container"><h3 class="server-name">' + escapeHTML(server.nome) + '</h3></div><span class="occurrence-badge">' + occurrenceText + '</span></div><div class="card-body">';

                server.links.forEach(link => {
                    const detalheExibir = link.info || link.detalhes || 'Nenhum detalhe adicional informado.';
                    const nomeArquivo = (link.arquivo || '').replace('.xlsx', '').replace('Local: ', '');
                    const nomeArquivoEscaped = escapeHTML(nomeArquivo);
                    const tagAbaHtml = link.aba ? '<span class="source-tag aba-tag">' + escapeHTML(link.aba) + '</span>' : '';
                    const tagRegionalHtml = link.regional ? '<span class="source-tag" style="background:#f0fdf4; border-color:#bbf7d0; color:#16a34a;"><svg viewBox="0 0 24 24" style="fill:none; stroke:currentColor; stroke-width:2; width:12px; height:12px; margin-right:2px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>' + escapeHTML(link.regional) + '</span>' : '';

                    html += '<div class="link-item"><div class="meta-field"><span class="meta-label">Matrícula</span><span class="meta-value highlight">' + escapeHTML(formatMatricula(link.matricula)) + '</span></div><div class="meta-field"><span class="meta-label">CPF</span><span class="meta-value highlight">' + escapeHTML(formatCPF(link.cpf)) + '</span></div><div class="meta-field"><span class="meta-label">Ação / Origem Jurídica</span><div class="meta-value" style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-top:0.25rem;"><button type="button" class="source-tag acao-tag clickable-tag" data-acao="' + nomeArquivoEscaped + '" title="Clique para abrir a planilha desta ação"><svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg><span>' + nomeArquivoEscaped + '</span></button>' + tagAbaHtml + tagRegionalHtml + '</div></div><div class="meta-field" style="grid-column: 1 / -1;"><span class="meta-label">Detalhes da Planilha</span><span class="meta-value info-tag">' + escapeHTML(detalheExibir) + '</span></div></div>';
                });

                html += '</div></div>';
            }
            html += '</div>';

            resultsContent.innerHTML = html;

            // Busca assíncrona das stats GM+FUNDEF para a regional
            (async () => {
                const bloco = document.getElementById('gm-fundef-regional-block');
                if (!bloco) return;
                try {
                    const res = await fetch('/api/stats/guilherme-fundef?regional=' + encodeURIComponent(data.regional));
                    const d = await res.json();
                    if (!d.success || (d.total_guilherme_melo === 0 && d.total_fundef === 0)) {
                        bloco.style.display = 'none';
                        return;
                    }
                    bloco.innerHTML = `
                        <div style="margin-bottom:1rem;">
                            <div style="display:flex;align-items:center;gap:0.65rem;margin-bottom:0.85rem;flex-wrap:wrap;">
                                <h3 style="font-family:'Outfit',sans-serif;color:var(--text-main);font-size:1.05rem;margin:0;">
                                    Guilherme Melo + FUNDEF em <span style="color:var(--accent);">${escapeHTML(data.regional)}</span>
                                </h3>
                                <span style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:6px;font-size:0.7rem;font-weight:700;padding:0.15rem 0.45rem;text-transform:uppercase;letter-spacing:0.5px;">Contagem por Matr&iacute;cula</span>
                            </div>
                            <div class="gm-stats-grid">
                                <div class="gm-stat-card total">
                                    <span class="sc-label">Total &Uacute;nico (Uni&atilde;o)</span>
                                    <span class="sc-num">${d.total_unico_conjunto}</span>
                                    <span class="sc-sub">Pessoas distintas nas duas a&ccedil;&otilde;es</span>
                                </div>
                                <div class="gm-stat-card gm">
                                    <span class="sc-label">Guilherme Melo</span>
                                    <span class="sc-num">${d.total_guilherme_melo}</span>
                                    <span class="sc-sub">${d.so_guilherme_melo} s&oacute; nesta a&ccedil;&atilde;o</span>
                                </div>
                                <div class="gm-stat-card fu">
                                    <span class="sc-label">FUNDEF</span>
                                    <span class="sc-num">${d.total_fundef}</span>
                                    <span class="sc-sub">${d.so_fundef} s&oacute; nesta a&ccedil;&atilde;o</span>
                                </div>
                                <div class="gm-stat-card inter">
                                    <span class="sc-label">Em Ambas as A&ccedil;&otilde;es</span>
                                    <span class="sc-num">${d.total_em_ambos}</span>
                                    <span class="sc-sub">Mesma matr&iacute;cula em GM e FUNDEF</span>
                                </div>
                            </div>
                        </div>
                    `;
                } catch (e) {
                    bloco.style.display = 'none';
                }
            })();
        }

        // Modal Event Handlers para Planilhas
        let planilhasData = [];

        const modalSenha = document.getElementById('modal-senha');
        const senhaAcessoInput = document.getElementById('senha-acesso-input');
        const senhaErroMsg = document.getElementById('senha-erro-msg');
        const btnCloseSenhaX = document.getElementById('btn-close-senha-x');
        const btnCancelSenha = document.getElementById('btn-cancel-senha');
        const btnConfirmarSenha = document.getElementById('btn-confirmar-senha');

        let pendingAcaoAbertura = null;

        // Clique em qualquer tag de Ação / Origem Jurídica
        document.addEventListener('click', (e) => {
            const acaoBtn = e.target.closest('.source-tag.acao-tag');
            if (acaoBtn) {
                e.preventDefault();
                e.stopPropagation();
                const nomeAcao = acaoBtn.getAttribute('data-acao');
                if (nomeAcao) {
                    tratarCliqueAcao(nomeAcao);
                }
            }
        });

        async function tratarCliqueAcao(nomeAcao) {
            const senhaSalva = sessionStorage.getItem('sinte_senha_planilhas');
            if (!senhaSalva) {
                pendingAcaoAbertura = nomeAcao;
                abrirModalSenha();
                return;
            }
            await abrirPlanilhaDireta(nomeAcao);
        }

        async function abrirPlanilhaDireta(nomeAcao) {
            const senhaSalva = sessionStorage.getItem('sinte_senha_planilhas') || '';
            if (!senhaSalva) {
                pendingAcaoAbertura = nomeAcao;
                abrirModalSenha();
                return;
            }

            if (Object.keys(mapaPlanilhasUrls).length === 0) {
                await inicializarMapaPlanilhas();
            }

            const limpo = (nomeAcao || '').replace('.xlsx', '').replace('.xls', '').replace('Local: ', '').toUpperCase().trim();

            let url = mapaPlanilhasUrls[limpo];

            // Busca flexível
            if (!url) {
                for (const k in mapaPlanilhasUrls) {
                    const kLimpo = k.replace('.XLSX', '').replace('.XLS', '').replace('LOCAL: ', '').trim();
                    if (limpo.includes(kLimpo) || kLimpo.includes(limpo)) {
                        url = mapaPlanilhasUrls[k];
                        break;
                    }
                }
            }

            // Fallback para Guilherme Melo / FUNDEF / Filiações
            if (!url) {
                if (limpo.includes("GUILHERME") || limpo.includes("FUNDEF") || limpo.includes("FILIA")) {
                    url = mapaPlanilhasUrls["AÇÃO GUILHERME MELO COMPLETO"] || "https://docs.google.com/spreadsheets/d/1-3xLtKtDB4VdSIC9C-HAyTdCZ_aQOPNkQcy9fvMG9-c/edit?usp=drivesdk";
                }
            }

            if (url) {
                if (url.startsWith('/planilhas/')) {
                    const urlComSenha = `${url}?senha=${encodeURIComponent(senhaSalva)}`;
                    const a = document.createElement('a');
                    a.href = urlComSenha;
                    a.download = '';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    showToast(`Baixando planilha "${nomeAcao}"...`, 'success');
                } else {
                    window.open(url, '_blank');
                    showToast(`Abrindo planilha "${nomeAcao}" no Google Sheets...`, 'success');
                }
            } else {
                modalPlanilhas.style.display = 'flex';
                modalSearchInput.value = nomeAcao;
                carregarPlanilhas();
                showToast('Planilha localizada no painel.', 'success');
            }
        }

        function abrirModalSenha() {
            modalSenha.style.display = 'flex';
            senhaAcessoInput.value = '';
            senhaErroMsg.style.display = 'none';
            senhaAcessoInput.focus();
        }

        function fecharModalSenha() {
            modalSenha.style.display = 'none';
            senhaAcessoInput.value = '';
            senhaErroMsg.style.display = 'none';
            pendingAcaoAbertura = null;
        }

        btnCloseSenhaX.addEventListener('click', fecharModalSenha);
        btnCancelSenha.addEventListener('click', fecharModalSenha);
        modalSenha.addEventListener('click', (e) => {
            if (e.target === modalSenha) {
                fecharModalSenha();
            }
        });

        senhaAcessoInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                validarSenhaSubmit();
            }
        });

        btnConfirmarSenha.addEventListener('click', validarSenhaSubmit);

        async function validarSenhaSubmit() {
            const senhaDigitada = senhaAcessoInput.value.trim();
            if (!senhaDigitada) {
                senhaErroMsg.textContent = 'Por favor, digite a senha.';
                senhaErroMsg.style.display = 'block';
                return;
            }

            btnConfirmarSenha.disabled = true;
            btnConfirmarSenha.textContent = 'Verificando...';
            senhaErroMsg.style.display = 'none';

            try {
                const response = await fetch('/api/planilhas', {
                    headers: { 'Authorization': senhaDigitada }
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    sessionStorage.setItem('sinte_senha_planilhas', senhaDigitada);

                    if (data.planilhas) {
                        planilhasData = data.planilhas;
                        data.planilhas.forEach(p => {
                            mapaPlanilhasUrls[p.nome.toUpperCase().trim()] = p.url;
                            if (p.url.startsWith('/planilhas/')) {
                                const filename = p.url.replace('/planilhas/', '');
                                mapaPlanilhasUrls[filename.toUpperCase().trim()] = p.url;
                                mapaPlanilhasUrls[filename.replace('.xlsx', '').replace('.xls', '').toUpperCase().trim()] = p.url;
                            }
                        });
                    }

                    const acaoParaAbrir = pendingAcaoAbertura;
                    fecharModalSenha();

                    if (acaoParaAbrir) {
                        await abrirPlanilhaDireta(acaoParaAbrir);
                    } else {
                        modalPlanilhas.style.display = 'flex';
                        modalSearchInput.value = '';
                        renderPlanilhas(planilhasData);
                        showToast('Acesso autorizado!', 'success');
                    }
                } else {
                    senhaErroMsg.textContent = data.error || 'Senha incorreta. Tente novamente.';
                    senhaErroMsg.style.display = 'block';
                }
            } catch (error) {
                console.error("Erro ao validar senha:", error);
                senhaErroMsg.textContent = 'Erro ao conectar ao servidor.';
                senhaErroMsg.style.display = 'block';
            } finally {
                btnConfirmarSenha.disabled = false;
                btnConfirmarSenha.textContent = 'Confirmar';
            }
        }

        async function carregarPlanilhas() {
            planilhasGrid.innerHTML = `
                <div class="planilhas-loading">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                    </svg>
                    <span>Carregando planilhas ativas...</span>
                </div>
            `;

            try {
                const senhaSalva = sessionStorage.getItem('sinte_senha_planilhas') || '';
                const response = await fetch('/api/planilhas', {
                    headers: { 'Authorization': senhaSalva }
                });
                const data = await response.json();

                if (response.status === 401 || !data.success) {
                    sessionStorage.removeItem('sinte_senha_planilhas');
                    fecharModalPlanilhas();
                    abrirModalSenha();
                    showToast(data.error || 'Acesso não autorizado.', 'error');
                    return;
                }

                if (data.success) {
                    planilhasData = data.planilhas;
                    renderPlanilhas(planilhasData);
                } else {
                    planilhasGrid.innerHTML = `
                        <div class="planilhas-loading" style="color: var(--danger);">
                            <h3>Erro ao carregar</h3>
                            <p>${data.error || 'Erro desconhecido'}</p>
                        </div>
                    `;
                }
            } catch (error) {
                console.error("Erro ao carregar planilhas:", error);
                planilhasGrid.innerHTML = `
                    <div class="planilhas-loading" style="color: var(--danger);">
                        <h3>Erro de conexão</h3>
                        <p>Não foi possível comunicar com o servidor.</p>
                    </div>
                `;
            }
        }

        function renderPlanilhas(planilhas) {
            if (planilhas.length === 0) {
                planilhasGrid.innerHTML = `
                    <div class="planilhas-loading">
                        <span>Nenhuma planilha correspondente encontrada.</span>
                    </div>
                `;
                return;
            }

            let html = '';
            planilhas.forEach(p => {
                const badgeText = p.tipo;
                const iconGoogle = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                        <polyline points="15 3 21 3 21 9"></polyline>
                        <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                `;
                const iconLocal = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                `;

                const btnIcon = p.local ? iconLocal : iconGoogle;
                const cardClass = p.local ? 'tipo-local' : 'tipo-google';

                const senhaSalva = sessionStorage.getItem('sinte_senha_planilhas') || '';
                const urlComSenha = p.local ? `${p.url}?senha=${encodeURIComponent(senhaSalva)}` : p.url;
                const linkAttr = p.local ? `href="${urlComSenha}" download` : `href="${p.url}" target="_blank"`;
                const tooltipText = p.local ? 'Clique para baixar a planilha Excel' : 'Clique para abrir no Google Sheets';

                html += `
                    <a ${linkAttr} class="planilha-card ${cardClass}" title="${tooltipText}">
                        <div class="planilha-info">
                            <span class="planilha-type-badge">
                                <svg viewBox="0 0 24 24" fill="currentColor">
                                    <circle cx="12" cy="12" r="10"></circle>
                                </svg>
                                ${badgeText}
                            </span>
                            <div class="planilha-name">${escapeHTML(p.nome)}</div>
                        </div>
                        <div class="planilha-link-icon">
                            ${btnIcon}
                        </div>
                    </a>
                `;
            });
            planilhasGrid.innerHTML = html;
        }

        btnOpenPlanilhas.addEventListener('click', () => {
            const senhaSalva = sessionStorage.getItem('sinte_senha_planilhas');
            if (senhaSalva) {
                modalPlanilhas.style.display = 'flex';
                modalSearchInput.value = '';
                carregarPlanilhas();
            } else {
                abrirModalSenha();
            }
        });

        const fecharModalPlanilhas = () => {
            modalPlanilhas.style.display = 'none';
        };

        btnCloseModal.addEventListener('click', fecharModalPlanilhas);
        btnCloseModalX.addEventListener('click', fecharModalPlanilhas);

        modalPlanilhas.addEventListener('click', (e) => {
            if (e.target === modalPlanilhas) {
                fecharModalPlanilhas();
            }
        });

        modalSearchInput.addEventListener('input', () => {
            const query = modalSearchInput.value.toLowerCase().trim();
            const filtradas = planilhasData.filter(p => p.nome.toLowerCase().includes(query));
            renderPlanilhas(filtradas);
        });

        // Controle do Modal de Atualização
        const modalAtualizacao = document.getElementById('modal-atualizacao');
        const btnCloseAtualizacao = document.getElementById('btn-close-atualizacao');
        const btnCloseAtualizacaoX = document.getElementById('btn-close-atualizacao-x');
        const btnNovidades = document.getElementById('btn-novidades');
        const tipDestaqueCpf = document.getElementById('tip-destaque-cpf');

        const abrirModalAtualizacao = () => {
            if (modalAtualizacao) modalAtualizacao.style.display = 'flex';
        };

        const fecharModalAtualizacao = () => {
            if (modalAtualizacao) modalAtualizacao.style.display = 'none';
        };

        if (btnCloseAtualizacao) btnCloseAtualizacao.addEventListener('click', fecharModalAtualizacao);
        if (btnCloseAtualizacaoX) btnCloseAtualizacaoX.addEventListener('click', fecharModalAtualizacao);
        if (btnNovidades) btnNovidades.addEventListener('click', abrirModalAtualizacao);
        if (tipDestaqueCpf) tipDestaqueCpf.addEventListener('click', abrirModalAtualizacao);

        if (modalAtualizacao) {
            modalAtualizacao.addEventListener('click', (e) => {
                if (e.target === modalAtualizacao) {
                    fecharModalAtualizacao();
                }
            });

            // Exibe automaticamente o aviso da atualização do CPF se ainda não visto
            if (!localStorage.getItem('sinte_atualizacao_cpf_zero_v3')) {
                setTimeout(() => {
                    abrirModalAtualizacao();
                    localStorage.setItem('sinte_atualizacao_cpf_zero_v3', 'true');
                }, 600);
            }
        }

        // ==============================================================
        // LÓGICA DO MÓDULO DE GESTÃO DE HERDEIROS (SINTE-PI)
        // ==============================================================
        let listaHerdeirosCache = [];
        let casoHerdeiroAtual = null;
        let herdeirosViewModo = 'kanban';
        let herdeiroIdParaArquivar = null;
        let filtroStatusKpi = '';

        const STATUS_MAP_TEXT = {
            'fila_espera': 'Fila de Espera (Doc Recebida)',
            'em_producao': 'Em Produção',
            'enviado_assinatura': 'Enviado p/ Assinatura',
            'concluido': 'Concluído & Arquivado'
        };

        // --- INICIALIZAÇÃO E CARREGAMENTO DE DADOS ---
        async function carregarHerdeiros() {
            try {
                const searchVal = document.getElementById('herdeiros-search-input')?.value || '';
                const acaoVal = document.getElementById('herdeiros-filter-acao')?.value || 'TODAS';
                const caixaVal = document.getElementById('herdeiros-filter-caixa')?.value || 'TODAS';

                let url = '/api/herdeiros?';
                const params = [];
                if (searchVal.trim()) params.push('q=' + encodeURIComponent(searchVal.trim()));
                if (filtroStatusKpi) params.push('status=' + encodeURIComponent(filtroStatusKpi));
                if (acaoVal !== 'TODAS') params.push('acao=' + encodeURIComponent(acaoVal));
                if (caixaVal !== 'TODAS') params.push('caixa=' + encodeURIComponent(caixaVal));
                url += params.join('&');

                const res = await fetch(url);
                const data = await res.json();
                if (data.success) {
                    listaHerdeirosCache = data.herdeiros || [];
                    renderizarVisaoHerdeiros();
                }
                await atualizarStatsHerdeiros();
            } catch (err) {
                console.error('Erro ao carregar herdeiros:', err);
                showToast('Erro ao carregar lista de herdeiros.', 'error');
            }
        }

        async function atualizarStatsHerdeiros() {
            try {
                const res = await fetch('/api/herdeiros/stats');
                const data = await res.json();
                if (data.success && data.stats) {
                    const st = data.stats;
                    const countEspera = document.getElementById('kpi-count-espera');
                    const countProducao = document.getElementById('kpi-count-producao');
                    const countAssinatura = document.getElementById('kpi-count-assinatura');
                    const countConcluido = document.getElementById('kpi-count-concluido');

                    if (countEspera) countEspera.textContent = st.fila_espera || 0;
                    if (countProducao) countProducao.textContent = st.em_producao || 0;
                    if (countAssinatura) countAssinatura.textContent = st.enviado_assinatura || 0;
                    if (countConcluido) countConcluido.textContent = st.concluido || 0;

                    const totalPendentes = (st.fila_espera || 0) + (st.em_producao || 0) + (st.enviado_assinatura || 0);
                    if (badgeHerdeirosPendentes) {
                        badgeHerdeirosPendentes.textContent = totalPendentes;
                        badgeHerdeirosPendentes.style.display = totalPendentes > 0 ? 'inline-block' : 'none';
                    }
                }
            } catch (err) {
                console.error('Erro ao buscar stats de herdeiros:', err);
            }
        }

        async function carregarCaixasFiltro() {
            try {
                const selectCaixa = document.getElementById('herdeiros-filter-caixa');
                const datalistCaixas = document.getElementById('caixas-existentes-list');
                if (!selectCaixa) return;

                const res = await fetch('/api/herdeiros/caixas');
                const data = await res.json();
                if (data.success && data.caixas) {
                    const caixas = data.caixas;
                    const valorAtual = selectCaixa.value;

                    let optionsHtml = '<option value="TODAS">Todas as Caixas Físicas</option>';
                    let datalistHtml = '';

                    caixas.forEach(c => {
                        optionsHtml += `<option value="${escapeHTML(c.nome)}">${escapeHTML(c.nome)} (${c.total})</option>`;
                        datalistHtml += `<option value="${escapeHTML(c.nome)}">`;
                    });

                    selectCaixa.innerHTML = optionsHtml;
                    selectCaixa.value = valorAtual || 'TODAS';

                    if (datalistCaixas) {
                        datalistCaixas.innerHTML = datalistHtml;
                    }
                }
            } catch (err) {
                console.error('Erro ao carregar caixas para filtro:', err);
            }
        }

        // --- RENDERIZAÇÃO KANBAN E TABELA ---
        function renderizarVisaoHerdeiros() {
            if (herdeirosViewModo === 'kanban') {
                renderizarKanban(listaHerdeirosCache);
            } else {
                renderizarTabela(listaHerdeirosCache);
            }
        }

        function formatarTempoAtras(dataStr) {
            if (!dataStr) return 'Recente';
            try {
                const partes = dataStr.split(' ');
                const partesData = partes[0].split('-');
                if (partesData.length === 3) {
                    const dataObj = new Date(partesData[0], partesData[1] - 1, partesData[2]);
                    const diffDias = Math.floor((new Date() - dataObj) / (1000 * 60 * 60 * 24));
                    if (diffDias <= 0) return 'Hoje';
                    if (diffDias === 1) return 'Ontem';
                    return `Há ${diffDias} dias`;
                }
            } catch (e) { }
            return dataStr.substring(0, 10);
        }

        function renderizarKanban(casos) {
            const colunas = {
                'fila_espera': document.getElementById('cards-wrapper-espera'),
                'em_producao': document.getElementById('cards-wrapper-producao'),
                'enviado_assinatura': document.getElementById('cards-wrapper-assinatura'),
                'concluido': document.getElementById('cards-wrapper-concluido')
            };

            const contadores = {
                'fila_espera': document.getElementById('count-badge-espera'),
                'em_producao': document.getElementById('count-badge-producao'),
                'enviado_assinatura': document.getElementById('count-badge-assinatura'),
                'concluido': document.getElementById('count-badge-concluido')
            };

            // Limpa colunas
            Object.values(colunas).forEach(col => { if (col) col.innerHTML = ''; });
            const counts = { fila_espera: 0, em_producao: 0, enviado_assinatura: 0, concluido: 0 };

            casos.forEach(caso => {
                const st = (caso.status || 'fila_espera').toLowerCase();
                if (colunas[st]) {
                    counts[st] = (counts[st] || 0) + 1;
                    const cardHtml = criarCardKanbanHtml(caso);
                    colunas[st].insertAdjacentHTML('beforeend', cardHtml);
                }
            });

            // Atualiza contadores
            Object.keys(counts).forEach(k => {
                if (contadores[k]) contadores[k].textContent = counts[k];
            });

            // Empty states nas colunas vazias
            Object.keys(colunas).forEach(k => {
                const col = colunas[k];
                if (col && counts[k] === 0) {
                    col.innerHTML = `
                        <div style="text-align: center; padding: 2rem 0.5rem; color: #94a3b8; font-size: 0.82rem;">
                            <span>Nenhum processo nesta fase</span>
                        </div>
                    `;
                }
            });
        }

        function criarCardKanbanHtml(caso) {
            const fal = caso.falecido || {};
            const herds = caso.herdeiros || [];
            const herdeiroPrincipal = herds.find(h => h.is_principal) || herds[0] || {};
            const tempoStr = formatarTempoAtras(caso.ultima_atualizacao || caso.data_cadastro);

            // Badge de localização física
            let localBadgeHtml = '';
            if (caso.status === 'concluido' && caso.caixa_concluido) {
                localBadgeHtml = `<span class="card-location-badge loc-caixa-concluido" title="Arquivado na caixa">📦 ${escapeHTML(caso.caixa_concluido)}</span>`;
            } else if (caso.localizacao_provisoria) {
                localBadgeHtml = `<span class="card-location-badge loc-provisorio" title="Guarda provisória">📁 ${escapeHTML(caso.localizacao_provisoria)}</span>`;
            }

            // Info de herdeiro para contato rápido
            let contatoHerdeiroHtml = '';
            if (herdeiroPrincipal && herdeiroPrincipal.nome) {
                const telExibir = herdeiroPrincipal.telefone || 'Sem telefone';
                const parentescoTxt = herdeiroPrincipal.parentesco ? ` (${herdeiroPrincipal.parentesco})` : '';
                contatoHerdeiroHtml = `
                    <div class="card-herdeiro-info">
                        <span class="herdeiro-label">Herdeiro Responsável:</span>
                        <div class="herdeiro-name-row">
                            <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 170px;">
                                ${escapeHTML(herdeiroPrincipal.nome)}${escapeHTML(parentescoTxt)}
                            </span>
                            <span style="font-size: 0.72rem; color: #64748b;">${escapeHTML(telExibir)}</span>
                        </div>
                    </div>
                `;
            }

            // Ações específicas de rodapé conforme o estágio
            let botoesRodape = '';
            if (caso.status === 'fila_espera') {
                botoesRodape = `
                    <button type="button" class="btn-card-action btn-action-primary" onclick="event.stopPropagation(); transicionarStatus('${escapeHTML(caso.id)}', 'em_producao');" title="Iniciar elaboração da minuta jurídica">
                        <span>▶ Iniciar Produção</span>
                    </button>
                    <button type="button" class="btn-card-action" style="background:#f1f5f9; color:#475569;" onclick="event.stopPropagation(); abrirModalDetalhesHerdeiro('${escapeHTML(caso.id)}');">
                        <span>Detalhes</span>
                    </button>
                `;
            } else if (caso.status === 'em_producao') {
                botoesRodape = `
                    <button type="button" class="btn-card-action btn-action-primary" onclick="event.stopPropagation(); transicionarStatus('${escapeHTML(caso.id)}', 'enviado_assinatura');" title="Minuta concluída: avançar para envio aos herdeiros">
                        <span>✅ Documento Pronto</span>
                    </button>
                    <button type="button" class="btn-card-action" style="background:#f1f5f9; color:#475569;" onclick="event.stopPropagation(); abrirModalDetalhesHerdeiro('${escapeHTML(caso.id)}');">
                        <span>Detalhes</span>
                    </button>
                `;
            } else if (caso.status === 'enviado_assinatura') {
                const telDigits = (herdeiroPrincipal.telefone || '').replace(/\D/g, '');
                const btnWhats = telDigits ? `
                    <button type="button" class="btn-card-action btn-whatsapp" onclick="event.stopPropagation(); dispararWhatsAppHerdeiro('${escapeHTML(caso.id)}', '${telDigits}', '${escapeHTML(herdeiroPrincipal.nome || '')}', '${escapeHTML(fal.nome || '')}', '${escapeHTML(fal.acao_juridica || '')}');" title="Abrir WhatsApp com texto pronto">
                        <span>💬 WhatsApp</span>
                    </button>
                ` : '';
                botoesRodape = `
                    ${btnWhats}
                    <button type="button" class="btn-card-action btn-concluir" onclick="event.stopPropagation(); abrirModalArquivar('${escapeHTML(caso.id)}');" title="Herdeiros assinaram: arquivar na caixa definitiva">
                        <span>🗃️ Arquivar</span>
                    </button>
                `;
            } else {
                botoesRodape = `
                    <button type="button" class="btn-card-action" style="background:#ecfdf5; color:#047857; border-color:#a7f3d0;" onclick="event.stopPropagation(); abrirModalDetalhesHerdeiro('${escapeHTML(caso.id)}');">
                        <span>👁️ Ver Ficha Completa</span>
                    </button>
                `;
            }

            // Contagem de checklist
            const chk = caso.documentos_checklist || {};
            const qtdDocs = Object.keys(chk).filter(k => k !== 'outros' && chk[k] === true).length;
            const docBadge = `<span class="meta-pill" style="background:#f8fafc; border:1px solid #e2e8f0;">📄 ${qtdDocs}/7 docs</span>`;

            return `
                <div class="kanban-card" onclick="abrirModalDetalhesHerdeiro('${escapeHTML(caso.id)}')">
                    <div class="card-top">
                        <span class="card-id-badge">${escapeHTML(caso.id)}</span>
                        <span class="card-time-badge">⏱️ ${tempoStr}</span>
                    </div>

                    <div class="card-falecido-nome">${escapeHTML(fal.nome || 'SEM NOME')}</div>

                    <div class="card-meta-pills">
                        <span class="meta-pill pill-acao">${escapeHTML(fal.acao_juridica || 'Ação Geral')}</span>
                        ${fal.cpf ? `<span class="meta-pill">CPF: ${escapeHTML(formatCPF(fal.cpf))}</span>` : ''}
                        ${fal.matricula ? `<span class="meta-pill">Mat: ${escapeHTML(formatMatricula(fal.matricula))}</span>` : ''}
                        ${docBadge}
                    </div>

                    ${contatoHerdeiroHtml}
                    ${localBadgeHtml}

                    <div class="card-actions-footer">
                        ${botoesRodape}
                    </div>
                </div>
            `;
        }

        function renderizarTabela(casos) {
            const tbody = document.getElementById('herdeiros-table-body');
            if (!tbody) return;

            if (casos.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">Nenhum processo de herdeiros encontrado com os filtros atuais.</td></tr>`;
                return;
            }

            let html = '';
            casos.forEach(c => {
                const fal = c.falecido || {};
                const herds = c.herdeiros || [];
                const principal = herds.find(h => h.is_principal) || herds[0] || {};
                const st = c.status || 'fila_espera';
                const stLabel = STATUS_MAP_TEXT[st] || st;

                const localTxt = (st === 'concluido' && c.caixa_concluido)
                    ? `📦 <strong>${escapeHTML(c.caixa_concluido)}</strong>`
                    : `📁 ${escapeHTML(c.localizacao_provisoria || 'Recepção')}`;

                html += `
                    <tr onclick="abrirModalDetalhesHerdeiro('${escapeHTML(c.id)}')" style="cursor: pointer;">
                        <td><span class="card-id-badge">${escapeHTML(c.id)}</span></td>
                        <td><strong>${escapeHTML(fal.nome || '---')}</strong></td>
                        <td>${escapeHTML(formatCPF(fal.cpf || ''))} / ${escapeHTML(formatMatricula(fal.matricula || ''))}</td>
                        <td><span class="meta-pill pill-acao">${escapeHTML(fal.acao_juridica || '---')}</span></td>
                        <td>${escapeHTML(principal.nome || '---')} ${principal.telefone ? `<br><small style="color:#64748b;">${escapeHTML(principal.telefone)}</small>` : ''}</td>
                        <td>${localTxt}</td>
                        <td><span class="status-badge status-${st}">${stLabel}</span></td>
                        <td style="text-align: right;" onclick="event.stopPropagation();">
                            <button type="button" class="btn-outline-action" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="abrirModalDetalhesHerdeiro('${escapeHTML(c.id)}');">
                                <span>Abrir</span>
                            </button>
                        </td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;
        }

        // --- NAVEGAÇÃO E TRANSIÇÕES DE VISÃO ---
        const btnViewKanban = document.getElementById('btn-view-kanban');
        const btnViewTabela = document.getElementById('btn-view-tabela');
        const kanbanView = document.getElementById('herdeiros-kanban-view');
        const tableView = document.getElementById('herdeiros-table-view');

        if (btnViewKanban) {
            btnViewKanban.addEventListener('click', () => {
                herdeirosViewModo = 'kanban';
                btnViewKanban.classList.add('active');
                if (btnViewTabela) btnViewTabela.classList.remove('active');
                if (kanbanView) kanbanView.style.display = 'grid';
                if (tableView) tableView.style.display = 'none';
                renderizarVisaoHerdeiros();
            });
        }

        if (btnViewTabela) {
            btnViewTabela.addEventListener('click', () => {
                herdeirosViewModo = 'tabela';
                btnViewTabela.classList.add('active');
                if (btnViewKanban) btnViewKanban.classList.remove('active');
                if (kanbanView) kanbanView.style.display = 'none';
                if (tableView) tableView.style.display = 'block';
                renderizarVisaoHerdeiros();
            });
        }

        // Cliques nos KPI cards para filtrar por status
        const kpiCards = [
            { id: 'kpi-card-espera', status: 'fila_espera' },
            { id: 'kpi-card-producao', status: 'em_producao' },
            { id: 'kpi-card-assinatura', status: 'enviado_assinatura' },
            { id: 'kpi-card-concluido', status: 'concluido' }
        ];

        kpiCards.forEach(item => {
            const el = document.getElementById(item.id);
            if (el) {
                el.addEventListener('click', () => {
                    if (filtroStatusKpi === item.status) {
                        filtroStatusKpi = ''; // Toggle off
                        el.style.borderColor = '';
                    } else {
                        filtroStatusKpi = item.status;
                        kpiCards.forEach(c => {
                            const other = document.getElementById(c.id);
                            if (other) other.style.borderColor = '';
                        });
                        el.style.borderColor = 'var(--accent)';
                    }
                    carregarHerdeiros();
                });
            }
        });

        // Eventos dos filtros da Toolbar
        const inputBuscaHerdeiro = document.getElementById('herdeiros-search-input');
        if (inputBuscaHerdeiro) {
            let debounceBusca;
            inputBuscaHerdeiro.addEventListener('input', () => {
                clearTimeout(debounceBusca);
                debounceBusca = setTimeout(() => {
                    carregarHerdeiros();
                }, 300);
            });
        }

        const filterAcaoHerdeiro = document.getElementById('herdeiros-filter-acao');
        if (filterAcaoHerdeiro) {
            filterAcaoHerdeiro.addEventListener('change', () => carregarHerdeiros());
        }

        const filterCaixaHerdeiro = document.getElementById('herdeiros-filter-caixa');
        if (filterCaixaHerdeiro) {
            filterCaixaHerdeiro.addEventListener('change', () => carregarHerdeiros());
        }

        const btnExportarHerdeiros = document.getElementById('btn-exportar-herdeiros');
        if (btnExportarHerdeiros) {
            btnExportarHerdeiros.addEventListener('click', () => {
                window.location.href = '/api/herdeiros/exportar';
                showToast('Gerando exportação Excel dos Herdeiros...', 'info');
            });
        }

        // --- TRANSIÇÃO RÁPIDA DE STATUS ---
        async function transicionarStatus(id, novoStatus, caixa = '', obs = '') {
            try {
                const res = await fetch(`/api/herdeiros/${encodeURIComponent(id)}/mover-status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        novo_status: novoStatus,
                        caixa_concluido: caixa,
                        observacao: obs
                    })
                });
                const data = await res.json();
                if (data.success) {
                    showToast(`Processo ${id} movido para: ${STATUS_MAP_TEXT[novoStatus] || novoStatus}!`, 'success');
                    await carregarHerdeiros();
                    if (casoHerdeiroAtual && casoHerdeiroAtual.id === id) {
                        await abrirModalDetalhesHerdeiro(id);
                    }
                } else {
                    showToast(data.error || 'Erro ao mover processo.', 'error');
                }
            } catch (err) {
                console.error('Erro na transição:', err);
                showToast('Erro de comunicação com o servidor.', 'error');
            }
        }

        // --- DISPARO DE WHATSAPP ---
        async function dispararWhatsAppHerdeiro(casoId, telefone, nomeHerdeiro, nomeFalecido, acaoJuridica) {
            const digits = (telefone || '').replace(/\D/g, '');
            if (!digits) {
                showToast('Herdeiro sem telefone cadastrado.', 'error');
                return;
            }

            const dddNumero = digits.length <= 11 ? '55' + digits : digits;
            const textoMensagem = `Olá, ${nomeHerdeiro || 'tudo bem'}! Aqui é do Departamento Jurídico do SINTE-PI.\n\nInformamos que a produção/documentação referente ao processo de habilitação de herdeiros de *${nomeFalecido}* (*${acaoJuridica || 'Ação Jurídica'}*) está pronta para conferência e assinatura.\n\nPor favor, entre em contato ou compareça ao sindicato para darmos prosseguimento ao arquivamento.`;

            const urlWhats = `https://api.whatsapp.com/send?phone=${dddNumero}&text=${encodeURIComponent(textoMensagem)}`;
            window.open(urlWhats, '_blank');

            // Registra notificação no backend
            try {
                await fetch(`/api/herdeiros/${encodeURIComponent(casoId)}/notificar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        canal: 'whatsapp',
                        destinatario: `${nomeHerdeiro} (${digits})`,
                        texto: textoMensagem
                    })
                });
                showToast('Notificação WhatsApp registrada no histórico!', 'success');
            } catch (e) {
                console.error('Erro ao registrar notificação:', e);
            }
        }

        // --- MODAL DE CADASTRO / EDIÇÃO DE HERDEIROS ---
        const modalCadHerdeiro = document.getElementById('modal-herdeiro-cadastro');
        const btnNovoHerdeiro = document.getElementById('btn-novo-herdeiro');
        const btnCloseCadHerdeiroX = document.getElementById('btn-close-cad-herdeiro-x');
        const btnCancelCadHerdeiro = document.getElementById('btn-cancel-cad-herdeiro');
        const btnSalvarCadHerdeiro = document.getElementById('btn-salvar-cad-herdeiro');
        const btnAddHerdeiroCard = document.getElementById('btn-add-herdeiro-card');
        const containerHerdeirosCards = document.getElementById('cad-herdeiros-cards-container');
        let filtroHerdeiroAtual = 'todos';

        function aplicarFiltroHerdeiros() {
            if (!containerHerdeirosCards) return;

            const cards = containerHerdeirosCards.querySelectorAll('.dynamic-heir-card');
            cards.forEach(card => {
                const parentesco = (card.querySelector('.h-parentesco')?.value || '').toLowerCase();
                const principal = card.querySelector('.h-principal')?.checked;
                let mostrar = true;

                if (filtroHerdeiroAtual === 'principal') {
                    mostrar = !!principal;
                } else if (filtroHerdeiroAtual === 'filhos') {
                    mostrar = /filho|filha|cônjuge|viúvo|viúva/.test(parentesco);
                } else if (filtroHerdeiroAtual === 'outros') {
                    mostrar = !(/filho|filha|cônjuge|viúvo|viúva/.test(parentesco));
                }

                card.style.display = mostrar ? 'block' : 'none';
            });
        }

        function configurarFiltroHerdeiros() {
            document.querySelectorAll('.herdeiros-filter-chip').forEach(botao => {
                botao.addEventListener('click', () => {
                    filtroHerdeiroAtual = botao.dataset.filter || 'todos';
                    document.querySelectorAll('.herdeiros-filter-chip').forEach(item => item.classList.toggle('active', item === botao));
                    aplicarFiltroHerdeiros();
                });
            });
        }

        if (btnNovoHerdeiro) {
            btnNovoHerdeiro.addEventListener('click', () => abrirModalCadastroHerdeiro());
        }
        if (btnCloseCadHerdeiroX) btnCloseCadHerdeiroX.addEventListener('click', fecharModalCadastroHerdeiro);
        if (btnCancelCadHerdeiro) btnCancelCadHerdeiro.addEventListener('click', fecharModalCadastroHerdeiro);

        function abrirModalCadastroHerdeiro(caso = null) {
            if (!modalCadHerdeiro) return;
            const editIdInput = document.getElementById('cad-herd-id-editando');
            const titleEl = document.getElementById('cad-modal-title');

            if (caso) {
                if (titleEl) titleEl.textContent = `Editar Processo de Herdeiros (${caso.id})`;
                if (editIdInput) editIdInput.value = caso.id;

                const fal = caso.falecido || {};
                document.getElementById('cad-falecido-nome').value = fal.nome || '';
                document.getElementById('cad-falecido-cpf').value = fal.cpf || '';
                document.getElementById('cad-falecido-matricula').value = fal.matricula || '';
                document.getElementById('cad-falecido-regional').value = fal.regional || '';
                document.getElementById('cad-falecido-acao').value = fal.acao_juridica || 'Ação Guilherme Melo';
                document.getElementById('cad-falecido-obito').value = fal.data_obito || '';
                document.getElementById('cad-local-provisorio').value = caso.localizacao_provisoria || '';
                document.getElementById('cad-caixa-concluido').value = caso.caixa_concluido || '';
                document.getElementById('cad-observacoes').value = caso.observacoes || '';

                // Checklist
                const chk = caso.documentos_checklist || {};
                document.getElementById('chk-doc-obito').checked = !!chk.certidao_obito;
                document.getElementById('chk-doc-rg-falecido').checked = !!chk.rg_cpf_falecido;
                document.getElementById('chk-doc-rg-herdeiros').checked = !!chk.rg_cpf_herdeiros;
                document.getElementById('chk-doc-residencia').checked = !!chk.comprovante_residencia;
                document.getElementById('chk-doc-dependentes').checked = !!chk.declaracao_dependentes;
                document.getElementById('chk-doc-casamento').checked = !!chk.certidao_casamento_nascimento;
                document.getElementById('chk-doc-procuracao').checked = !!chk.procuracao;
                document.getElementById('cad-doc-outros').value = chk.outros || '';

                // Herdeiros
                if (containerHerdeirosCards) containerHerdeirosCards.innerHTML = '';
                const herds = caso.herdeiros || [];
                if (herds.length > 0) {
                    herds.forEach(h => adicionarLinhaHerdeiro(h));
                } else {
                    adicionarLinhaHerdeiro();
                }
            } else {
                if (titleEl) titleEl.textContent = 'Registrar Entrada de Herdeiros';
                if (editIdInput) editIdInput.value = '';

                // Reseta formulário
                document.getElementById('cad-falecido-nome').value = '';
                document.getElementById('cad-falecido-cpf').value = '';
                document.getElementById('cad-falecido-matricula').value = '';
                document.getElementById('cad-falecido-regional').value = '';
                document.getElementById('cad-falecido-acao').value = 'Ação Guilherme Melo';
                document.getElementById('cad-falecido-obito').value = '';
                document.getElementById('cad-local-provisorio').value = 'Recepção / Entrada Jurídico';
                document.getElementById('cad-caixa-concluido').value = '';
                document.getElementById('cad-observacoes').value = '';

                document.getElementById('chk-doc-obito').checked = true;
                document.getElementById('chk-doc-rg-falecido').checked = true;
                document.getElementById('chk-doc-rg-herdeiros').checked = true;
                document.getElementById('chk-doc-residencia').checked = true;
                document.getElementById('chk-doc-dependentes').checked = false;
                document.getElementById('chk-doc-casamento').checked = false;
                document.getElementById('chk-doc-procuracao').checked = false;
                document.getElementById('cad-doc-outros').value = '';

                if (containerHerdeirosCards) containerHerdeirosCards.innerHTML = '';
                adicionarLinhaHerdeiro({ parentesco: 'Filho(a)', is_principal: true });
            }

            modalCadHerdeiro.style.display = 'flex';
        }

        function fecharModalCadastroHerdeiro() {
            if (modalCadHerdeiro) modalCadHerdeiro.style.display = 'none';
        }

        function adicionarLinhaHerdeiro(dados = null) {
            if (!containerHerdeirosCards) return;
            const index = containerHerdeirosCards.children.length + 1;
            const hNome = dados?.nome || '';
            const hParentesco = dados?.parentesco || 'Herdeiro(a)';
            const hCpf = dados?.cpf || '';
            const hTel = dados?.telefone || '';
            const hEmail = dados?.email || '';
            const hPrincipal = dados?.is_principal ? 'checked' : (index === 1 ? 'checked' : '');

            const card = document.createElement('div');
            card.className = 'dynamic-heir-card';
            card.dataset.principal = (hPrincipal === 'checked' || index === 1).toString();
            card.innerHTML = `
                <div class="heir-card-header">
                    <span class="heir-card-title">Herdeiro #${index}</span>
                    <span class="heir-card-badge">${hPrincipal === 'checked' || index === 1 ? 'Principal' : 'Herdeiro'}</span>
                    ${index > 1 ? `<button type="button" class="btn-remove-heir" onclick="this.closest('.dynamic-heir-card').remove(); aplicarFiltroHerdeiros();">✕ Remover</button>` : ''}
                </div>
                <div class="form-row-3">
                    <div class="form-group">
                        <label>Nome do Herdeiro *</label>
                        <input type="text" class="form-control h-nome" placeholder="Nome completo..." value="${escapeHTML(hNome)}" required>
                    </div>
                    <div class="form-group">
                        <label>Parentesco</label>
                        <select class="form-control h-parentesco">
                            <option value="Cônjuge / Viúvo(a)" ${hParentesco.includes('Cônjuge') ? 'selected' : ''}>Cônjuge / Viúvo(a)</option>
                            <option value="Filho(a)" ${hParentesco.includes('Filho') ? 'selected' : ''}>Filho(a)</option>
                            <option value="Pai / Mãe" ${hParentesco.includes('Pai') ? 'selected' : ''}>Pai / Mãe</option>
                            <option value="Irmão(ã)" ${hParentesco.includes('Irmão') ? 'selected' : ''}>Irmão(ã)</option>
                            <option value="Neto(a)" ${hParentesco.includes('Neto') ? 'selected' : ''}>Neto(a)</option>
                            <option value="Outro Parentesco" ${(!hParentesco.includes('Cônjuge') && !hParentesco.includes('Filho') && !hParentesco.includes('Pai') && !hParentesco.includes('Irmão') && !hParentesco.includes('Neto')) ? 'selected' : ''}>Outro</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>CPF do Herdeiro</label>
                        <input type="text" class="form-control h-cpf" placeholder="000.000.000-00" value="${escapeHTML(hCpf)}">
                    </div>
                </div>
                <div class="form-row-2">
                    <div class="form-group">
                        <label>WhatsApp / Telefone *</label>
                        <input type="text" class="form-control h-tel" placeholder="(86) 90000-0000" value="${escapeHTML(hTel)}">
                    </div>
                    <div class="form-group">
                        <label>E-mail</label>
                        <input type="email" class="form-control h-email" placeholder="email@exemplo.com" value="${escapeHTML(hEmail)}">
                    </div>
                </div>
                <div style="margin-top: 0.25rem;">
                    <label style="font-size: 0.78rem; display: inline-flex; align-items: center; gap: 0.35rem; cursor: pointer; color: var(--text-main); font-weight: 600;">
                        <input type="checkbox" class="h-principal" ${hPrincipal}>
                        <span>Contato Principal para Avisos / WhatsApp</span>
                    </label>
                </div>
            `;

            card.querySelector('.h-principal')?.addEventListener('change', () => {
                const checkboxPrincipal = card.querySelector('.h-principal');
                if (checkboxPrincipal?.checked) {
                    containerHerdeirosCards.querySelectorAll('.h-principal').forEach(outroCheckbox => {
                        if (outroCheckbox !== checkboxPrincipal) {
                            outroCheckbox.checked = false;
                            outroCheckbox.closest('.dynamic-heir-card')?.setAttribute('data-principal', 'false');
                            const outroBadge = outroCheckbox.closest('.dynamic-heir-card')?.querySelector('.heir-card-badge');
                            if (outroBadge) outroBadge.textContent = 'Herdeiro';
                        }
                    });
                }
                card.dataset.principal = (card.querySelector('.h-principal')?.checked || false).toString();
                const badge = card.querySelector('.heir-card-badge');
                if (badge) badge.textContent = card.querySelector('.h-principal')?.checked ? 'Principal' : 'Herdeiro';
                aplicarFiltroHerdeiros();
            });

            containerHerdeirosCards.appendChild(card);
            aplicarFiltroHerdeiros();

            card.querySelector('.h-parentesco')?.addEventListener('change', aplicarFiltroHerdeiros);
        }

        if (btnAddHerdeiroCard) {
            btnAddHerdeiroCard.addEventListener('click', () => adicionarLinhaHerdeiro());
        }

        configurarFiltroHerdeiros();

        // Helper de Auto-preenchimento ao buscar falecido no banco
        const btnCadBuscarTitular = document.getElementById('btn-cad-buscar-titular');
        const inputCadBuscaTitular = document.getElementById('cad-busca-titular-input');
        const boxSugestoesTitular = document.getElementById('cad-titular-sugestoes');

        async function buscarTitularHelper() {
            const query = inputCadBuscaTitular ? inputCadBuscaTitular.value.trim() : '';
            if (!query || query.length < 2) {
                showToast('Digite ao menos 2 caracteres para buscar o titular.', 'info');
                return;
            }

            try {
                const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                const resultados = data.results || [];

                if (resultados.length === 0) {
                    if (boxSugestoesTitular) {
                        boxSugestoesTitular.style.display = 'block';
                        boxSugestoesTitular.innerHTML = `<div style="padding:0.65rem; color:#64748b; font-size:0.82rem;">Nenhum registro encontrado no banco SINTE para "${escapeHTML(query)}". Preencha manualmente os campos abaixo.</div>`;
                    }
                    return;
                }

                if (boxSugestoesTitular) {
                    boxSugestoesTitular.style.display = 'block';
                    let listHtml = '';
                    resultados.slice(0, 8).forEach((r, idx) => {
                        const nome = r.nome || 'SEM NOME';
                        const cpf = r.cpf || 'Sem CPF';
                        const mat = r.matricula || 'Sem Matrícula';
                        const arq = r.arquivo || '';
                        const reg = r.regional || '';
                        listHtml += `
                            <div class="sugestao-item" style="padding:0.6rem 0.8rem; border-bottom:1px solid #f1f5f9; cursor:pointer; font-size:0.85rem;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background=''" onclick="selecionarTitularSugestao('${escapeHTML(nome)}', '${escapeHTML(cpf)}', '${escapeHTML(mat)}', '${escapeHTML(reg)}', '${escapeHTML(arq)}')">
                                <strong style="color:var(--text-main);">${escapeHTML(nome)}</strong>
                                <span style="display:block; font-size:0.75rem; color:#64748b;">CPF: ${escapeHTML(cpf)} • Mat: ${escapeHTML(mat)} • Regional: ${escapeHTML(reg || 'N/I')} • ${escapeHTML(arq)}</span>
                            </div>
                        `;
                    });
                    boxSugestoesTitular.innerHTML = listHtml;
                }
            } catch (err) {
                console.error('Erro no helper de busca:', err);
                showToast('Erro ao consultar banco do SINTE.', 'error');
            }
        }

        function selecionarTitularSugestao(nome, cpf, mat, regional, acao) {
            document.getElementById('cad-falecido-nome').value = nome;
            document.getElementById('cad-falecido-cpf').value = cpf;
            document.getElementById('cad-falecido-matricula').value = mat;
            document.getElementById('cad-falecido-regional').value = regional;

            const selectAcao = document.getElementById('cad-falecido-acao');
            if (selectAcao) {
                let achou = false;
                for (let i = 0; i < selectAcao.options.length; i++) {
                    if (acao.toUpperCase().includes(selectAcao.options[i].value.toUpperCase())) {
                        selectAcao.selectedIndex = i;
                        achou = true;
                        break;
                    }
                }
                if (!achou) selectAcao.value = 'Ação Guilherme Melo';
            }

            if (boxSugestoesTitular) boxSugestoesTitular.style.display = 'none';
            showToast(`Dados de ${nome} preenchidos com sucesso!`, 'success');
        }

        if (btnCadBuscarTitular) btnCadBuscarTitular.addEventListener('click', buscarTitularHelper);
        if (inputCadBuscaTitular) {
            inputCadBuscaTitular.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    buscarTitularHelper();
                }
            });
        }

        // Salvar cadastro de herdeiro
        if (btnSalvarCadHerdeiro) {
            btnSalvarCadHerdeiro.addEventListener('click', async () => {
                const nomeFalecido = document.getElementById('cad-falecido-nome').value.trim();
                if (!nomeFalecido) {
                    showToast('Informe o nome do titular falecido.', 'error');
                    document.getElementById('cad-falecido-nome').focus();
                    return;
                }

                // Coleta herdeiros
                const herdeirosList = [];
                const heirCards = containerHerdeirosCards.querySelectorAll('.dynamic-heir-card');
                heirCards.forEach(card => {
                    const nome = card.querySelector('.h-nome')?.value.trim();
                    if (nome) {
                        herdeirosList.push({
                            nome: nome,
                            parentesco: card.querySelector('.h-parentesco')?.value || 'Herdeiro(a)',
                            cpf: card.querySelector('.h-cpf')?.value.trim() || '',
                            telefone: card.querySelector('.h-tel')?.value.trim() || '',
                            email: card.querySelector('.h-email')?.value.trim() || '',
                            is_principal: card.querySelector('.h-principal')?.checked || false
                        });
                    }
                });

                if (herdeirosList.length === 0) {
                    showToast('Cadastre ao menos 1 herdeiro com nome.', 'error');
                    return;
                }

                const checklist = {
                    certidao_obito: document.getElementById('chk-doc-obito').checked,
                    rg_cpf_falecido: document.getElementById('chk-doc-rg-falecido').checked,
                    rg_cpf_herdeiros: document.getElementById('chk-doc-rg-herdeiros').checked,
                    comprovante_residencia: document.getElementById('chk-doc-residencia').checked,
                    declaracao_dependentes: document.getElementById('chk-doc-dependentes').checked,
                    certidao_casamento_nascimento: document.getElementById('chk-doc-casamento').checked,
                    procuracao: document.getElementById('chk-doc-procuracao').checked,
                    outros: document.getElementById('cad-doc-outros').value.trim()
                };

                const editId = document.getElementById('cad-herd-id-editando').value.trim();
                const payload = {
                    falecido: {
                        nome: nomeFalecido,
                        cpf: document.getElementById('cad-falecido-cpf').value.trim(),
                        matricula: document.getElementById('cad-falecido-matricula').value.trim(),
                        regional: document.getElementById('cad-falecido-regional').value.trim(),
                        acao_juridica: document.getElementById('cad-falecido-acao').value,
                        data_obito: document.getElementById('cad-falecido-obito').value
                    },
                    herdeiros: herdeirosList,
                    documentos_checklist: checklist,
                    localizacao_provisoria: document.getElementById('cad-local-provisorio').value.trim() || 'Recepção / Entrada Jurídico',
                    caixa_concluido: document.getElementById('cad-caixa-concluido').value.trim(),
                    observacoes: document.getElementById('cad-observacoes').value.trim()
                };

                try {
                    btnSalvarCadHerdeiro.disabled = true;
                    btnSalvarCadHerdeiro.textContent = 'Salvando...';

                    let res;
                    if (editId) {
                        res = await fetch(`/api/herdeiros/${encodeURIComponent(editId)}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                    } else {
                        res = await fetch('/api/herdeiros', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                    }

                    const data = await res.json();
                    if (data.success) {
                        showToast(editId ? `Processo ${editId} atualizado!` : `Entrada ${data.id} registrada com sucesso!`, 'success');
                        fecharModalCadastroHerdeiro();
                        await carregarHerdeiros();
                        if (editId) {
                            await abrirModalDetalhesHerdeiro(editId);
                        }
                    } else {
                        showToast(data.error || 'Erro ao salvar processo.', 'error');
                    }
                } catch (err) {
                    console.error('Erro ao salvar:', err);
                    showToast('Erro de comunicação ao salvar herdeiro.', 'error');
                } finally {
                    btnSalvarCadHerdeiro.disabled = false;
                    btnSalvarCadHerdeiro.textContent = 'Salvar Processo de Herdeiros';
                }
            });
        }

        // --- MODAL DE DETALHES & HISTÓRICO ---
        const modalDetHerdeiro = document.getElementById('modal-herdeiro-detalhes');
        const btnCloseDetHerdeiroX = document.getElementById('btn-close-det-herdeiro-x');
        const btnCloseDetHerdeiro = document.getElementById('btn-close-det-herdeiro');
        const btnDetEditar = document.getElementById('btn-det-editar');
        const btnDetExcluir = document.getElementById('btn-det-excluir');
        const btnImprimirFicha = document.getElementById('btn-imprimir-ficha');
        const btnEnviarAnexo = document.getElementById('btn-enviar-anexo');

        if (btnCloseDetHerdeiroX) btnCloseDetHerdeiroX.addEventListener('click', () => { if (modalDetHerdeiro) modalDetHerdeiro.style.display = 'none'; });
        if (btnCloseDetHerdeiro) btnCloseDetHerdeiro.addEventListener('click', () => { if (modalDetHerdeiro) modalDetHerdeiro.style.display = 'none'; });

        async function abrirModalDetalhesHerdeiro(id) {
            try {
                const res = await fetch(`/api/herdeiros/${encodeURIComponent(id)}`);
                const data = await res.json();
                if (!data.success || !data.caso) {
                    showToast('Processo de herdeiro não encontrado.', 'error');
                    return;
                }

                const caso = data.caso;
                casoHerdeiroAtual = caso;
                const fal = caso.falecido || {};

                // Header
                document.getElementById('det-caso-id').textContent = caso.id;
                const stBadge = document.getElementById('det-caso-status-badge');
                stBadge.className = `status-badge status-${caso.status || 'fila_espera'}`;
                stBadge.textContent = STATUS_MAP_TEXT[caso.status] || caso.status;

                document.getElementById('det-caso-nome-falecido').textContent = fal.nome || 'SEM NOME';
                document.getElementById('det-caso-subtitulo').textContent = `CPF: ${formatCPF(fal.cpf || 'S/N')} • Matrícula: ${formatMatricula(fal.matricula || 'S/N')} • Ação: ${fal.acao_juridica || 'Geral'} • Regional: ${fal.regional || 'N/I'}`;

                // Botões de transição
                const boxTransicoes = document.getElementById('det-botoes-transicao');
                let btnsTransHtml = '';
                if (caso.status === 'fila_espera') {
                    btnsTransHtml = `<button type="button" class="btn-card-action btn-action-primary" style="padding:0.4rem 0.8rem;" onclick="transicionarStatus('${escapeHTML(caso.id)}', 'em_producao')">▶ Iniciar Minuta (Mover p/ Em Produção)</button>`;
                } else if (caso.status === 'em_producao') {
                    btnsTransHtml = `<button type="button" class="btn-card-action btn-action-primary" style="padding:0.4rem 0.8rem;" onclick="transicionarStatus('${escapeHTML(caso.id)}', 'enviado_assinatura')">📤 Minuta Pronta (Mover p/ Enviado p/ Assinatura)</button>`;
                } else if (caso.status === 'enviado_assinatura') {
                    btnsTransHtml = `<button type="button" class="btn-card-action btn-concluir" style="padding:0.4rem 0.8rem;" onclick="abrirModalArquivar('${escapeHTML(caso.id)}')">🗃️ Assinado / Concluir na Caixa Específica</button>`;
                } else {
                    btnsTransHtml = `<span style="font-size:0.85rem; color:#047857; font-weight:700;">✅ Processo Arquivado em Definitivo</span>`;
                }
                if (boxTransicoes) boxTransicoes.innerHTML = btnsTransHtml;

                // Guarda Física
                const boxLoc = document.getElementById('det-localizacao-box');
                if (boxLoc) {
                    if (caso.status === 'concluido' && caso.caixa_concluido) {
                        boxLoc.innerHTML = `<span class="card-location-badge loc-caixa-concluido" style="font-size:0.95rem; padding:0.4rem 0.75rem;">📦 Caixa Definitiva: ${escapeHTML(caso.caixa_concluido)}</span>`;
                    } else {
                        boxLoc.innerHTML = `<span class="card-location-badge loc-provisorio" style="font-size:0.95rem; padding:0.4rem 0.75rem;">📁 Guarda Provisória: ${escapeHTML(caso.localizacao_provisoria || 'Recepção')}</span>`;
                    }
                }

                // Herdeiros
                const boxHerds = document.getElementById('det-herdeiros-lista');
                if (boxHerds) {
                    let herdsHtml = '';
                    const herds = caso.herdeiros || [];
                    if (herds.length === 0) {
                        herdsHtml = '<div style="color:#64748b; font-size:0.82rem;">Nenhum herdeiro registrado.</div>';
                    } else {
                        herds.forEach(h => {
                            const telDigits = (h.telefone || '').replace(/\D/g, '');
                            const btnWhats = telDigits ? `
                                <button type="button" class="btn-card-action btn-whatsapp" style="padding:0.3rem 0.6rem; font-size:0.75rem;" onclick="dispararWhatsAppHerdeiro('${escapeHTML(caso.id)}', '${telDigits}', '${escapeHTML(h.nome)}', '${escapeHTML(fal.nome)}', '${escapeHTML(fal.acao_juridica)}')">
                                    💬 WhatsApp
                                </button>
                            ` : '';

                            const btnMail = h.email ? `
                                <a href="mailto:${escapeHTML(h.email)}?subject=SINTE-PI%20-%20Processo%20de%20Herdeiros%20${encodeURIComponent(fal.nome)}" class="btn-outline-action" style="padding:0.3rem 0.6rem; font-size:0.75rem; text-decoration:none;">
                                    ✉️ E-mail
                                </a>
                            ` : '';

                            herdsHtml += `
                                <div style="background:#ffffff; border:1px solid var(--surface-border); border-radius:8px; padding:0.65rem 0.85rem;">
                                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                                        <div>
                                            <strong style="font-size:0.9rem; color:var(--text-main);">${escapeHTML(h.nome)}</strong>
                                            ${h.is_principal ? '<span style="background:#eff6ff; color:#1d4ed8; font-size:0.68rem; font-weight:700; padding:0.1rem 0.35rem; border-radius:4px; margin-left:0.35rem;">PRINCIPAL</span>' : ''}
                                            <span style="display:block; font-size:0.75rem; color:#64748b;">${escapeHTML(h.parentesco || 'Herdeiro')} • CPF: ${escapeHTML(formatCPF(h.cpf || '---'))}</span>
                                            <span style="display:block; font-size:0.78rem; color:var(--text-main); font-weight:600; margin-top:0.2rem;">📞 ${escapeHTML(h.telefone || 'Sem telefone')}</span>
                                        </div>
                                        <div style="display:flex; gap:0.35rem;">
                                            ${btnWhats}
                                            ${btnMail}
                                        </div>
                                    </div>
                                </div>
                            `;
                        });
                    }
                    boxHerds.innerHTML = herdsHtml;
                }

                // Checklist
                const boxChk = document.getElementById('det-checklist-view');
                if (boxChk) {
                    const chk = caso.documentos_checklist || {};
                    const itens = [
                        { label: 'Certidão de Óbito do Titular', val: chk.certidao_obito },
                        { label: 'RG e CPF do Titular Falecido', val: chk.rg_cpf_falecido },
                        { label: 'RG e CPF dos Herdeiros', val: chk.rg_cpf_herdeiros },
                        { label: 'Comprovante de Residência', val: chk.comprovante_residencia },
                        { label: 'Declaração de Inexistência de Dependentes (INSS/RPPS)', val: chk.declaracao_dependentes },
                        { label: 'Certidão de Casamento / Nascimento', val: chk.certidao_casamento_nascimento },
                        { label: 'Procuração Jurídica Assinada', val: chk.procuracao }
                    ];

                    let chkHtml = '';
                    itens.forEach(it => {
                        const icon = it.val ? '✅' : '⚪';
                        const cor = it.val ? '#047857' : '#94a3b8';
                        chkHtml += `<div style="display:flex; align-items:center; gap:0.45rem; color:${cor};"><span>${icon}</span> <span>${escapeHTML(it.label)}</span></div>`;
                    });
                    if (chk.outros) {
                        chkHtml += `<div style="margin-top:0.4rem; padding-top:0.4rem; border-top:1px dashed #e2e8f0; font-size:0.78rem; color:#475569;"><strong>Outros:</strong> ${escapeHTML(chk.outros)}</div>`;
                    }
                    boxChk.innerHTML = chkHtml;
                }

                // Anexos
                const boxAnexos = document.getElementById('det-anexos-lista');
                if (boxAnexos) {
                    const anexos = caso.anexos || [];
                    if (anexos.length === 0) {
                        boxAnexos.innerHTML = '<div style="color:#64748b; font-size:0.8rem; padding:0.35rem 0;">Nenhum arquivo digitalizado anexado ainda.</div>';
                    } else {
                        let anexosHtml = '';
                        anexos.forEach(a => {
                            anexosHtml += `
                                <div style="display:flex; align-items:center; justify-content:space-between; background:#f8fafc; border:1px solid var(--surface-border); border-radius:6px; padding:0.45rem 0.65rem; font-size:0.8rem;">
                                    <div>
                                        <strong style="color:var(--text-main); display:block;">${escapeHTML(a.original_name || a.filename)}</strong>
                                        <span style="color:#64748b; font-size:0.72rem;">${escapeHTML(a.tipo || 'Documento')} • ${escapeHTML(a.data_upload || '')}</span>
                                    </div>
                                    <a href="${escapeHTML(a.url)}" target="_blank" class="btn-outline-action" style="padding:0.25rem 0.5rem; font-size:0.72rem; text-decoration:none;">
                                        <span>Visualizar</span>
                                    </a>
                                </div>
                            `;
                        });
                        boxAnexos.innerHTML = anexosHtml;
                    }
                }

                // Histórico Timeline
                const boxTimeline = document.getElementById('det-timeline-view');
                if (boxTimeline) {
                    const hist = (caso.historico || []).slice().reverse();
                    let histHtml = '';
                    hist.forEach(ev => {
                        histHtml += `
                            <div class="timeline-event">
                                <div class="timeline-header">
                                    <span>${escapeHTML(ev.acao)}</span>
                                    <span class="timeline-date">${escapeHTML(ev.data)}</span>
                                </div>
                                <div class="timeline-details">${escapeHTML(ev.detalhes || '')} ${ev.usuario ? `• <em style="font-size:0.7rem;">${escapeHTML(ev.usuario)}</em>` : ''}</div>
                            </div>
                        `;
                    });
                    boxTimeline.innerHTML = histHtml || '<div style="color:#64748b; font-size:0.8rem;">Nenhum evento registrado.</div>';
                }

                if (modalDetHerdeiro) modalDetHerdeiro.style.display = 'flex';
            } catch (err) {
                console.error('Erro ao abrir detalhes:', err);
                showToast('Erro ao carregar detalhes do caso.', 'error');
            }
        }

        // Upload de anexo
        if (btnEnviarAnexo) {
            btnEnviarAnexo.addEventListener('click', async () => {
                if (!casoHerdeiroAtual) return;
                const fileInput = document.getElementById('upload-arquivo-input');
                const tipoSelect = document.getElementById('upload-tipo-anexo');

                if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
                    showToast('Selecione um arquivo para enviar.', 'error');
                    return;
                }

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('tipo', tipoSelect ? tipoSelect.value : 'Documento');

                try {
                    btnEnviarAnexo.disabled = true;
                    btnEnviarAnexo.textContent = 'Enviando...';

                    const res = await fetch(`/api/herdeiros/${encodeURIComponent(casoHerdeiroAtual.id)}/anexos`, {
                        method: 'POST',
                        body: formData
                    });
                    const data = await res.json();
                    if (data.success) {
                        showToast('Arquivo anexado com sucesso!', 'success');
                        fileInput.value = '';
                        await abrirModalDetalhesHerdeiro(casoHerdeiroAtual.id);
                    } else {
                        showToast(data.error || 'Erro ao fazer upload.', 'error');
                    }
                } catch (err) {
                    console.error('Erro no upload:', err);
                    showToast('Erro ao enviar anexo.', 'error');
                } finally {
                    btnEnviarAnexo.disabled = false;
                    btnEnviarAnexo.textContent = 'Upload';
                }
            });
        }

        // Editar caso do modal de detalhes
        if (btnDetEditar) {
            btnDetEditar.addEventListener('click', () => {
                if (casoHerdeiroAtual) {
                    if (modalDetHerdeiro) modalDetHerdeiro.style.display = 'none';
                    abrirModalCadastroHerdeiro(casoHerdeiroAtual);
                }
            });
        }

        // Excluir caso do modal de detalhes
        if (btnDetExcluir) {
            btnDetExcluir.addEventListener('click', async () => {
                if (!casoHerdeiroAtual) return;
                const confirma = confirm(`Tem certeza que deseja remover o processo de herdeiros de ${casoHerdeiroAtual.falecido?.nome || casoHerdeiroAtual.id}? Esta ação não pode ser desfeita.`);
                if (!confirma) return;

                try {
                    const res = await fetch(`/api/herdeiros/${encodeURIComponent(casoHerdeiroAtual.id)}`, {
                        method: 'DELETE'
                    });
                    const data = await res.json();
                    if (data.success) {
                        showToast(`Processo ${casoHerdeiroAtual.id} excluído com sucesso.`, 'success');
                        if (modalDetHerdeiro) modalDetHerdeiro.style.display = 'none';
                        await carregarHerdeiros();
                    } else {
                        showToast(data.error || 'Erro ao excluir.', 'error');
                    }
                } catch (err) {
                    console.error('Erro na exclusão:', err);
                    showToast('Erro de comunicação ao excluir processo.', 'error');
                }
            });
        }

        // Impressão da Ficha de Protocolo
        if (btnImprimirFicha) {
            btnImprimirFicha.addEventListener('click', () => {
                if (!casoHerdeiroAtual) return;
                const c = casoHerdeiroAtual;
                const fal = c.falecido || {};

                document.getElementById('print-protocol-id').textContent = c.id;
                document.getElementById('print-data-cadastro').textContent = `Data de Entrada: ${c.data_cadastro || ''}`;
                document.getElementById('print-local-caixa').textContent = (c.status === 'concluido' && c.caixa_concluido)
                    ? `Caixa: ${c.caixa_concluido}`
                    : `Local Provisório: ${c.localizacao_provisoria || 'Recepção'}`;

                document.getElementById('print-falecido-nome').textContent = fal.nome || '---';
                document.getElementById('print-falecido-cpf').textContent = formatCPF(fal.cpf || '---');
                document.getElementById('print-falecido-mat').textContent = formatMatricula(fal.matricula || '---');
                document.getElementById('print-falecido-regional').textContent = fal.regional || 'N/I';
                document.getElementById('print-falecido-acao').textContent = fal.acao_juridica || '---';

                const boxPrintHerds = document.getElementById('print-herdeiros-lista');
                if (boxPrintHerds) {
                    let listHtml = '';
                    (c.herdeiros || []).forEach((h, i) => {
                        listHtml += `<p style="margin:2px 0;"><strong>${i + 1}. ${escapeHTML(h.nome)}</strong> (${escapeHTML(h.parentesco || 'Herdeiro')}) • CPF: ${escapeHTML(formatCPF(h.cpf || 'S/N'))} • Tel: ${escapeHTML(h.telefone || 'S/N')}</p>`;
                    });
                    boxPrintHerds.innerHTML = listHtml;
                }

                const boxPrintChk = document.getElementById('print-checklist-docs');
                if (boxPrintChk) {
                    const chk = c.documentos_checklist || {};
                    let chkHtml = '';
                    const lista = [
                        { label: 'Certidão de Óbito', val: chk.certidao_obito },
                        { label: 'RG e CPF do Titular Falecido', val: chk.rg_cpf_falecido },
                        { label: 'RG e CPF dos Herdeiros', val: chk.rg_cpf_herdeiros },
                        { label: 'Comprovante de Residência', val: chk.comprovante_residencia },
                        { label: 'Declaração Inexistência de Dependentes', val: chk.declaracao_dependentes },
                        { label: 'Certidão Casamento/Nascimento', val: chk.certidao_casamento_nascimento },
                        { label: 'Procuração Jurídica', val: chk.procuracao }
                    ];
                    lista.forEach(item => {
                        chkHtml += `<span style="margin-right:15px; display:inline-block;">[${item.val ? 'X' : ' '}] ${item.label}</span> `;
                    });
                    if (chk.outros) chkHtml += `<br><span>Outros: ${escapeHTML(chk.outros)}</span>`;
                    boxPrintChk.innerHTML = chkHtml;
                }

                window.print();
            });
        }

        // --- MODAL DE ARQUIVAMENTO EM CAIXA ---
        const modalArquivar = document.getElementById('modal-herdeiro-arquivar');
        const btnCloseArquivarX = document.getElementById('btn-close-arquivar-x');
        const btnCancelArquivar = document.getElementById('btn-cancel-arquivar');
        const btnConfirmarArquivar = document.getElementById('btn-confirmar-arquivar');

        function abrirModalArquivar(id) {
            herdeiroIdParaArquivar = id;
            const inputCaixa = document.getElementById('arquivar-caixa-nome');
            const inputObs = document.getElementById('arquivar-caixa-obs');
            if (inputCaixa) inputCaixa.value = '';
            if (inputObs) inputObs.value = '';
            if (modalArquivar) modalArquivar.style.display = 'flex';
        }

        if (btnCloseArquivarX) btnCloseArquivarX.addEventListener('click', () => { if (modalArquivar) modalArquivar.style.display = 'none'; });
        if (btnCancelArquivar) btnCancelArquivar.addEventListener('click', () => { if (modalArquivar) modalArquivar.style.display = 'none'; });

        if (btnConfirmarArquivar) {
            btnConfirmarArquivar.addEventListener('click', async () => {
                if (!herdeiroIdParaArquivar) return;
                const caixaNome = document.getElementById('arquivar-caixa-nome')?.value.trim();
                if (!caixaNome) {
                    showToast('Informe o nome ou número da Caixa Física.', 'error');
                    return;
                }
                const obs = document.getElementById('arquivar-caixa-obs')?.value.trim() || '';

                await transicionarStatus(herdeiroIdParaArquivar, 'concluido', caixaNome, obs);
                if (modalArquivar) modalArquivar.style.display = 'none';
            });
        }

        // --- MODAL DE GESTÃO DE CAIXAS FÍSICAS ---
        const modalCaixas = document.getElementById('modal-caixas-gerenciador');
        const btnAbrirCaixas = document.getElementById('btn-abrir-caixas');
        const btnCloseCaixasX = document.getElementById('btn-close-caixas-x');
        const btnCloseCaixas = document.getElementById('btn-close-caixas');
        const btnVoltarCaixas = document.getElementById('btn-voltar-caixas');
        const containerCaixasGrid = document.getElementById('caixas-grid-container');
        const containerCaixaDetalhes = document.getElementById('caixa-detalhes-container');

        if (btnAbrirCaixas) btnAbrirCaixas.addEventListener('click', abrirModalCaixas);
        if (btnCloseCaixasX) btnCloseCaixasX.addEventListener('click', () => { if (modalCaixas) modalCaixas.style.display = 'none'; });
        if (btnCloseCaixas) btnCloseCaixas.addEventListener('click', () => { if (modalCaixas) modalCaixas.style.display = 'none'; });

        async function abrirModalCaixas() {
            if (!modalCaixas) return;
            if (containerCaixaDetalhes) containerCaixaDetalhes.style.display = 'none';
            if (containerCaixasGrid) containerCaixasGrid.style.display = 'grid';

            try {
                const res = await fetch('/api/herdeiros/caixas');
                const data = await res.json();
                if (data.success && containerCaixasGrid) {
                    const caixas = data.caixas || [];
                    if (caixas.length === 0) {
                        containerCaixasGrid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:3rem 1rem; color:#64748b;">Nenhuma caixa de arquivo registrada ainda. Conclua processos para arquivar em caixas.</div>`;
                    } else {
                        let html = '';
                        caixas.forEach(c => {
                            html += `
                                <div class="caixa-card" onclick="mostrarProcessosDaCaixa('${escapeHTML(c.nome)}')">
                                    <div class="caixa-card-header">
                                        <span class="caixa-icon">📦</span>
                                        <span class="caixa-total-badge">${c.total} processo(s)</span>
                                    </div>
                                    <div class="caixa-nome">${escapeHTML(c.nome)}</div>
                                    <span style="font-size:0.75rem; color:#64748b;">Clique para listar as pastas guardadas nesta caixa &raquo;</span>
                                </div>
                            `;
                        });
                        containerCaixasGrid.innerHTML = html;
                    }
                }
                modalCaixas.style.display = 'flex';
            } catch (err) {
                console.error('Erro ao listar caixas:', err);
                showToast('Erro ao carregar caixas de arquivo.', 'error');
            }
        }

        async function mostrarProcessosDaCaixa(nomeCaixa) {
            try {
                const res = await fetch('/api/herdeiros/caixas');
                const data = await res.json();
                if (data.success) {
                    const caixaObj = (data.caixas || []).find(c => c.nome === nomeCaixa);
                    if (!caixaObj) return;

                    if (containerCaixasGrid) containerCaixasGrid.style.display = 'none';
                    if (containerCaixaDetalhes) containerCaixaDetalhes.style.display = 'block';

                    document.getElementById('caixa-detalhes-titulo').textContent = `📦 ${nomeCaixa} (${caixaObj.total} processos)`;

                    const wrapper = document.getElementById('caixa-detalhes-tabela-wrapper');
                    let tableHtml = `
                        <table class="modern-table">
                            <thead>
                                <tr>
                                    <th>Código</th>
                                    <th>Titular Falecido</th>
                                    <th>CPF / Matrícula</th>
                                    <th>Ação Jurídica</th>
                                    <th style="text-align: right;">Ação</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;

                    caixaObj.casos.forEach(item => {
                        tableHtml += `
                            <tr>
                                <td><span class="card-id-badge">${escapeHTML(item.id)}</span></td>
                                <td><strong>${escapeHTML(item.falecido_nome || '---')}</strong></td>
                                <td>${escapeHTML(formatCPF(item.cpf || ''))} / ${escapeHTML(formatMatricula(item.matricula || ''))}</td>
                                <td><span class="meta-pill pill-acao">${escapeHTML(item.acao || '---')}</span></td>
                                <td style="text-align: right;">
                                    <button type="button" class="btn-outline-action" style="padding:0.25rem 0.5rem; font-size:0.75rem;" onclick="fecharModalCaixasEAbrirHerdeiro('${escapeHTML(item.id)}');">
                                        Ver Ficha
                                    </button>
                                </td>
                            </tr>
                        `;
                    });

                    tableHtml += `</tbody></table>`;
                    wrapper.innerHTML = tableHtml;
                }
            } catch (err) {
                console.error('Erro ao mostrar processos da caixa:', err);
            }
        }

        function fecharModalCaixasEAbrirHerdeiro(id) {
            if (modalCaixas) modalCaixas.style.display = 'none';
            abrirModalDetalhesHerdeiro(id);
        }

        if (btnVoltarCaixas) {
            btnVoltarCaixas.addEventListener('click', () => {
                if (containerCaixaDetalhes) containerCaixaDetalhes.style.display = 'none';
                if (containerCaixasGrid) containerCaixasGrid.style.display = 'grid';
            });
        }

        // --- ATALHO GERAL DE TRANSIÇÃO (CHAMADO POR QUALQUER TELA) ---
        function irParaHerdeiro(id) {
            if (tabHerdeiros) {
                tabHerdeiros.click();
                setTimeout(() => {
                    abrirModalDetalhesHerdeiro(id);
                }, 200);
            }
        }

        // Carrega contadores do badge logo na inicialização
        setTimeout(() => {
            atualizarStatsHerdeiros();
        }, 800);
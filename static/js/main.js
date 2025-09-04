// 全局变量
let usageChart = null;
let apiUsageChart = null;
let selectedGroupId = null;

// 显示Toast通知
function showToast(message, type = 'info') {
    const toastEl = document.getElementById('liveToast');
    const toastBody = toastEl.querySelector('.toast-body');
    const toastHeader = toastEl.querySelector('.toast-header i');
    
    toastBody.textContent = message;
    
    // 设置图标和颜色
    toastHeader.className = 'bi me-2';
    switch(type) {
        case 'success':
            toastHeader.classList.add('bi-check-circle', 'text-success');
            break;
        case 'error':
            toastHeader.classList.add('bi-x-circle', 'text-danger');
            break;
        case 'warning':
            toastHeader.classList.add('bi-exclamation-triangle', 'text-warning');
            break;
        default:
            toastHeader.classList.add('bi-info-circle', 'text-primary');
    }
    
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}

// 加载API密钥摘要
function loadApiKeysSummary() {
    $.get('/api/usage/summary', function(data) {
        updateOverviewCards(data);
        updateApiKeysTable(data);
    }).fail(function() {
        showToast('加载API密钥摘要失败', 'error');
    });
}

// 更新概览卡片
function updateOverviewCards(data) {
    let totalCount = data.length;
    let activeCount = 0;
    let totalUsage = 0;
    let totalLimit = 0;
    
    data.forEach(item => {
        // 用量超过99%视为用尽，不计入活跃
        if (item.usage_percentage < 99) activeCount++;
        totalUsage += item.character_count;
        totalLimit += item.character_limit;
    });
    
    $('#total-apis').text(totalCount);
    $('#active-apis').text(activeCount);
    
    // 格式化总用量为"万"单位
    const totalUsageFormatted = formatToWan(totalUsage);
    const totalLimitFormatted = formatToWan(totalLimit);
    $('#total-usage').text(`${totalUsageFormatted} / ${totalLimitFormatted}`);
    
    const avgUsageRate = totalLimit > 0 ? (totalUsage / totalLimit * 100).toFixed(1) : 0;
    $('#avg-usage-rate').text(avgUsageRate + '%');
}

// 格式化数字为万单位
function formatToWan(num) {
    if (num >= 100000000) {
        // 亿为单位
        const yi = Math.round(num / 10000000) / 10;
        return yi + '亿';
    } else if (num >= 10000) {
        // 万为单位，保留一位小数
        const wan = Math.round(num / 1000) / 10;
        // 如果是整数，不显示小数点
        if (wan === Math.floor(wan)) {
            return Math.floor(wan) + 'W';
        }
        return wan + 'W';
    }
    return formatNumber(num);
}

// 更新API密钥表格
function updateApiKeysTable(data) {
    const tbody = $('#api-keys-tbody');
    tbody.empty();
    
    data.forEach(item => {
        const usagePercent = item.usage_percentage.toFixed(1);
        const progressColor = getProgressColor(usagePercent);
        const lastCheck = item.last_check ? new Date(item.last_check).toLocaleString('zh-CN') : '从未检查';
        const groupName = groupsCache[item.group_id] || '未知组';
        
        // 处理状态显示
        let statusBadge = '';
        let statusIndicator = '';
        if (item.api_type === 'pro' && item.is_expired) {
            statusBadge = '<span class="badge bg-danger">已过期</span>';
            statusIndicator = '<span class="status-indicator inactive"></span>';
        } else if (item.character_limit === 0) {
            statusBadge = '<span class="badge bg-warning">未检查</span>';
            statusIndicator = '<span class="status-indicator inactive"></span>';
        } else if (item.usage_percentage >= 99) {
            statusBadge = '<span class="badge bg-danger">已用尽</span>';
            statusIndicator = '<span class="status-indicator inactive"></span>';
        } else if (item.usage_percentage >= 90) {
            statusBadge = '<span class="badge bg-warning">即将用尽</span>';
            statusIndicator = '<span class="status-indicator active"></span>';
        } else {
            statusBadge = '<span class="badge bg-success">正常</span>';
            statusIndicator = '<span class="status-indicator active"></span>';
        }
        
        const row = `
            <tr class="fade-in api-key-row" data-key-id="${item.key_id}" data-group-id="${item.group_id}" 
                data-api-key="${item.api_key || ''}" data-api-name="${item.key_name}"
                onclick="showApiDetails(${item.key_id})" style="cursor: pointer;">
                <td>
                    ${statusIndicator}
                    ${item.key_name}
                </td>
                <td>
                    <span class="badge bg-${item.api_type === 'pro' ? 'primary' : 'secondary'}">
                        ${item.api_type.toUpperCase()}
                    </span>
                </td>
                <td>${groupName}</td>
                <td>${item.character_limit > 0 ? formatNumber(item.character_count) + ' / ' + formatNumber(item.character_limit) : '未检查'}</td>
                <td>
                    <div class="progress" style="min-width: 100px;">
                        <div class="progress-bar bg-${progressColor}" style="width: ${usagePercent}%">
                            ${usagePercent}%
                        </div>
                    </div>
                </td>
                <td><small>${lastCheck}</small></td>
                <td>${statusBadge}</td>
                <td onclick="event.stopPropagation();">
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-success" onclick="checkSingleKey(${item.key_id})" title="立即检查">
                            <i class="bi bi-arrow-clockwise"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="deleteApiKey(${item.key_id})" title="删除">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

// 获取进度条颜色
function getProgressColor(percentage) {
    if (percentage < 50) return 'success';
    if (percentage < 80) return 'warning';
    return 'danger';
}

// 格式化数字
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// 存储组信息的全局变量
let groupsCache = {};

// 获取组名
function getGroupName(keyId) {
    // 从缓存中查找组名
    const groupItem = $(`.api-key-row[data-key-id="${keyId}"]`).data('group-id');
    if (groupItem && groupsCache[groupItem]) {
        return groupsCache[groupItem];
    }
    return '默认组';
}

// 加载组信息到缓存
function loadGroupsCache() {
    $.get('/api/groups', function(groups) {
        groups.forEach(group => {
            groupsCache[group.id] = group.name;
        });
    });
}

// 显示添加组模态框
function showAddGroupModal() {
    $('#addGroupModal').modal('show');
}

// 创建新组
function createGroup() {
    const name = $('#groupName').val();
    const queryInterval = parseInt($('#queryInterval').val());
    const isActive = $('#groupActive').is(':checked');
    
    if (!name) {
        showToast('请输入组名称', 'warning');
        return;
    }
    
    $.ajax({
        url: '/api/groups',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            name: name,
            query_interval: queryInterval,
            is_active: isActive
        }),
        success: function(response) {
            showToast('创建组成功', 'success');
            $('#addGroupModal').modal('hide');
            location.reload();
        },
        error: function() {
            showToast('创建组失败', 'error');
        }
    });
}

// 显示添加API密钥模态框
function showAddApiKeyModal() {
    $('#addApiKeyModal').modal('show');
}

// 添加API密钥
function addApiKey() {
    const name = $('#addApiKeyName').val();
    const apiKey = $('#addApiKeyValue').val();
    const groupId = $('#addApiKeyGroup').val();
    
    if (!apiKey) {
        showToast('请输入API密钥', 'warning');
        return;
    }
    
    $.ajax({
        url: '/api/keys',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            name: name || `API-${apiKey.slice(-8)}`,
            api_key: apiKey,
            group_id: parseInt(groupId)
        }),
        success: function(response) {
            showToast('添加API密钥成功', 'success');
            $('#addApiKeyModal').modal('hide');
            $('#addApiKeyForm')[0].reset();
            loadApiKeysSummary();
        },
        error: function(xhr) {
            const error = xhr.responseJSON;
            showToast(error.message || '添加API密钥失败', 'error');
        }
    });
}

// 删除API密钥
function deleteApiKey(keyId) {
    if (!confirm('确定要删除这个API密钥吗？')) {
        return;
    }
    
    $.ajax({
        url: `/api/keys/${keyId}`,
        method: 'DELETE',
        success: function() {
            showToast('删除成功', 'success');
            loadApiKeysSummary();
        },
        error: function() {
            showToast('删除失败', 'error');
        }
    });
}

// 立即检查指定组
function checkGroupNow(groupId) {
    $.get(`/api/check-now/${groupId}`, function(response) {
        showToast(response.message, 'success');
    }).fail(function() {
        showToast('检查失败', 'error');
    });
}

// 检查所有组
function checkAllGroups() {
    showToast('开始检查所有组的API用量...', 'info');
    // TODO: 实现检查所有组的功能
}

// 全局变量存储当前查看的API信息
let currentApiId = null;
let currentApiData = null;
let currentViewType = 'hour';

// 显示API详情
function showApiDetails(keyId) {
    currentApiId = keyId;
    
    // 先从行数据中获取基本信息
    const keyRow = $(`.api-key-row[data-key-id="${keyId}"]`);
    const apiName = keyRow.data('api-name');
    const apiKey = keyRow.data('api-key');
    
    // 获取API详细信息
    $.get(`/api/keys/${keyId}/details`, function(apiData) {
        currentApiData = apiData;
        
        // 填充基本信息
        $('#apiDetailTitle').text(`API密钥详情 - ${apiData.name}`);
        $('#apiKeyName').val(apiData.name);
        $('#apiKeyValue').val(apiData.api_key);
        $('#apiTypeDisplay').text(apiData.api_type.toUpperCase());
        $('#apiTypeDisplay').removeClass('bg-primary bg-secondary').addClass(apiData.api_type === 'pro' ? 'bg-primary' : 'bg-secondary');
        
        // 显示创建时间
        if (apiData.created_at) {
            $('#apiCreatedAt').text(new Date(apiData.created_at).toLocaleString('zh-CN'));
        } else {
            $('#apiCreatedAt').text('未知');
        }
        
        // 显示计费周期（仅Pro API）
        if (apiData.api_type === 'pro' && apiData.billing_start_time) {
            $('#billingPeriodDiv').show();
            $('#apiBillingStart').text(new Date(apiData.billing_start_time).toLocaleString('zh-CN'));
            $('#apiBillingEnd').text(new Date(apiData.billing_end_time).toLocaleString('zh-CN'));
            
            // 检查是否过期
            if (apiData.is_expired) {
                $('#apiExpiredBadge').show();
            } else {
                $('#apiExpiredBadge').hide();
            }
        } else {
            $('#billingPeriodDiv').hide();
        }
        
        // 更新用量进度条
        if (apiData.latest_usage) {
            const usage = apiData.latest_usage;
            // 对于Pro API，优先使用api_key_character_count/limit
            let characterCount = usage.character_count;
            let characterLimit = usage.character_limit;
            
            if (apiData.api_type === 'pro' && usage.api_key_character_count !== null && usage.api_key_character_count !== undefined) {
                characterCount = usage.api_key_character_count;
                characterLimit = usage.api_key_character_limit || 0;
            }
            
            const percentage = characterLimit > 0 ? (characterCount / characterLimit * 100).toFixed(1) : 0;
            const progressColor = getProgressColor(percentage);
            
            $('#apiUsageProgress')
                .removeClass('bg-success bg-warning bg-danger')
                .addClass(`bg-${progressColor}`)
                .css('width', `${percentage}%`)
                .text(`${percentage}%`);
            
            // 使用更友好的格式显示用量
            let usageText = '';
            if (characterCount >= 10000 || characterLimit >= 10000) {
                usageText = `${formatToWan(characterCount)} / ${formatToWan(characterLimit)}`;
            } else {
                usageText = `${formatNumber(characterCount)} / ${formatNumber(characterLimit)}`;
            }
            $('#apiUsageText').text(usageText);
        } else {
            $('#apiUsageProgress').css('width', '0%').text('0%');
            $('#apiUsageText').text('未检查');
        }
        
        // 重置视图选择
        $('#hourView').prop('checked', true);
        currentViewType = 'hour';
        
        // 加载用量数据
        loadUsageData('hour');
        
        // 显示模态框
        $('#apiDetailsModal').modal('show');
    }).fail(function() {
        // 如果API调用失败，至少显示基本信息
        $('#apiDetailTitle').text(`API密钥详情 - ${apiName || '未知'}`);
        $('#apiKeyName').val(apiName || '');
        $('#apiKeyValue').val(apiKey || '');
        $('#apiDetailsModal').modal('show');
        showToast('加载API详情失败', 'error');
    });
}

// 加载用量数据
function loadUsageData(period) {
    const hours = period === 'day' ? 720 : 24; // 30天或24小时
    
    $.get(`/api/usage/${currentApiId}?period=${period}&hours=${hours}`, function(data) {
        if (period === 'hour') {
            displayHourlyUsage(data);
        } else {
            displayDailyUsage(data);
        }
    }).fail(function() {
        showToast('加载用量数据失败', 'error');
    });
}

// 显示小时级用量
function displayHourlyUsage(records) {
    if (records.length === 0) {
        updateApiUsageChart(['暂无数据'], [0], '字符使用量（按小时）');
        return;
    }
    
    const labels = [];
    const usageData = [];
    
    records.reverse().forEach(record => {
        const time = new Date(record.check_time);
        labels.push(time.toLocaleString('zh-CN', { 
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit', 
            minute: '2-digit' 
        }));
        usageData.push(record.character_count);
    });
    
    updateApiUsageChart(labels, usageData, '字符使用量（按小时）');
}

// 显示天级用量
function displayDailyUsage(dailyData) {
    if (dailyData.length === 0) {
        updateApiUsageChart(['暂无数据'], [0], '字符使用量（按天）');
        return;
    }
    
    const labels = [];
    const usageData = [];
    
    dailyData.sort((a, b) => new Date(a.date) - new Date(b.date));
    
    dailyData.forEach(day => {
        labels.push(day.date);
        usageData.push(day.max_usage);
    });
    
    updateApiUsageChart(labels, usageData, '字符使用量（按天）');
}

// 切换用量视图
function switchUsageView(viewType) {
    currentViewType = viewType;
    loadUsageData(viewType);
}

// 启用密钥名称编辑
function enableKeyNameEdit() {
    $('#apiKeyName').prop('readonly', false).focus();
    $('.btn-outline-primary:has(.bi-pencil)').addClass('d-none');
    $('#saveKeyNameBtn, #cancelKeyNameBtn').removeClass('d-none');
}

// 取消密钥名称编辑
function cancelKeyNameEdit() {
    $('#apiKeyName').val(currentApiData.name).prop('readonly', true);
    $('.btn-outline-primary:has(.bi-pencil)').removeClass('d-none');
    $('#saveKeyNameBtn, #cancelKeyNameBtn').addClass('d-none');
}

// 保存密钥名称
function saveKeyName() {
    const newName = $('#apiKeyName').val().trim();
    
    if (!newName) {
        showToast('密钥名称不能为空', 'warning');
        return;
    }
    
    $.ajax({
        url: `/api/keys/${currentApiId}`,
        method: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({ name: newName }),
        success: function() {
            currentApiData.name = newName;
            $('#apiKeyName').prop('readonly', true);
            $('.btn-outline-primary:has(.bi-pencil)').removeClass('d-none');
            $('#saveKeyNameBtn, #cancelKeyNameBtn').addClass('d-none');
            showToast('密钥名称已更新', 'success');
            loadApiKeysSummary(); // 刷新列表
        },
        error: function() {
            showToast('更新密钥名称失败', 'error');
        }
    });
}

// 切换密钥可见性
function toggleKeyVisibility() {
    const keyInput = $('#apiKeyValue');
    const icon = $('#keyVisibilityIcon');
    const isShowing = keyInput.attr('data-show') === 'true';
    
    if (isShowing) {
        // 隐藏密钥
        keyInput.addClass('text-security-disc');
        keyInput.attr('data-show', 'false');
        icon.removeClass('bi-eye-slash').addClass('bi-eye');
    } else {
        // 显示密钥
        keyInput.removeClass('text-security-disc');
        keyInput.attr('data-show', 'true');
        icon.removeClass('bi-eye').addClass('bi-eye-slash');
    }
}

// 复制API密钥
function copyApiKey() {
    const keyInput = document.getElementById('apiKeyValue');
    
    // 选择文本
    keyInput.select();
    keyInput.setSelectionRange(0, 99999); // 移动设备兼容
    
    // 复制到剪贴板
    try {
        document.execCommand('copy');
        showToast('API密钥已复制到剪贴板', 'success');
    } catch (err) {
        // 如果失败，尝试使用新的Clipboard API
        if (navigator.clipboard) {
            navigator.clipboard.writeText(keyInput.value).then(function() {
                showToast('API密钥已复制到剪贴板', 'success');
            }, function() {
                showToast('复制失败，请手动复制', 'error');
            });
        } else {
            showToast('复制失败，请手动复制', 'error');
        }
    }
}

// 初始化用量图表
function initializeUsageChart() {
    const ctx = document.getElementById('usageChart').getContext('2d');
    
    usageChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '总用量',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

// 更新API用量图表
function updateApiUsageChart(labels, data, title = '字符使用量') {
    const ctx = document.getElementById('apiUsageChart').getContext('2d');
    
    if (apiUsageChart) {
        apiUsageChart.destroy();
    }
    
    apiUsageChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: title,
                data: data,
                borderColor: 'rgb(54, 162, 235)',
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                title: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + formatNumber(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

// 刷新API列表
function refreshApiList() {
    showToast('正在刷新...', 'info');
    loadApiKeysSummary();
}

// 显示组管理器
function showGroupManager() {
    // TODO: 实现组管理器UI
    showToast('组管理器开发中...', 'info');
}

// 显示组详情
function showGroupDetails(groupId) {
    selectedGroupId = groupId;
    $('.group-item').removeClass('active');
    $(`.group-item[data-group-id="${groupId}"]`).addClass('active');
    
    // 筛选显示该组的API密钥
    filterApiKeysByGroup(groupId);
}

// 根据组筛选API密钥
function filterApiKeysByGroup(groupId) {
    const allRows = $('.api-key-row');
    
    if (!groupId) {
        // 显示所有
        allRows.show();
        return;
    }
    
    allRows.each(function() {
        const row = $(this);
        const rowGroupId = row.data('group-id');
        
        if (rowGroupId == groupId) {
            row.show();
        } else {
            row.hide();
        }
    });
    
    // 更新标题或显示筛选信息
    const groupName = groupsCache[groupId] || '未知组';
    showToast(`正在显示 "${groupName}" 组的API密钥`, 'info');
}

// 显示所有API密钥
function showAllApiKeys() {
    selectedGroupId = null;
    $('.group-item').removeClass('active');
    $('.group-item[data-group-id=""]').addClass('active');
    
    // 显示所有API密钥
    $('.api-key-row').show();
    showToast('显示所有API密钥', 'info');
}

// 编辑组
function editGroup(groupId) {
    // 获取组信息
    $.get('/api/groups', function(groups) {
        const group = groups.find(g => g.id === groupId);
        if (group) {
            // 填充表单
            $('#editGroupId').val(group.id);
            $('#editGroupName').val(group.name);
            $('#editQueryInterval').val(group.query_interval);
            $('#editGroupActive').prop('checked', group.is_active);
            
            // 显示模态框
            $('#editGroupModal').modal('show');
        } else {
            showToast('未找到组信息', 'error');
        }
    }).fail(function() {
        showToast('获取组信息失败', 'error');
    });
}

// 更新组
function updateGroup() {
    const groupId = $('#editGroupId').val();
    const name = $('#editGroupName').val();
    const queryInterval = parseInt($('#editQueryInterval').val());
    const isActive = $('#editGroupActive').is(':checked');
    
    if (!name || queryInterval < 60) {
        showToast('请填写正确的信息', 'warning');
        return;
    }
    
    $.ajax({
        url: `/api/groups/${groupId}`,
        method: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({
            name: name,
            query_interval: queryInterval,
            is_active: isActive
        }),
        success: function() {
            showToast('更新成功', 'success');
            $('#editGroupModal').modal('hide');
            location.reload(); // 重新加载页面以更新组列表
        },
        error: function() {
            showToast('更新失败', 'error');
        }
    });
}

// 删除组
function deleteGroup() {
    const groupId = $('#editGroupId').val();
    const groupName = $('#editGroupName').val();
    
    // 检查是否还有API密钥
    let hasApiKeys = false;
    $('.api-key-row').each(function() {
        if ($(this).data('group-id') == groupId) {
            hasApiKeys = true;
            return false;
        }
    });
    
    let confirmMessage = `确定要删除组"${groupName}"吗？`;
    if (hasApiKeys) {
        confirmMessage += '\n\n⚠️ 警告：该组下的所有API密钥也将被删除！';
    }
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    $.ajax({
        url: `/api/groups/${groupId}`,
        method: 'DELETE',
        success: function() {
            showToast('删除成功', 'success');
            $('#editGroupModal').modal('hide');
            location.reload();
        },
        error: function() {
            showToast('删除失败', 'error');
        }
    });
}

// 检查单个API密钥
function checkSingleKey(keyId) {
    // 找到该密钥所属的组ID
    const keyRow = $(`.api-key-row[data-key-id="${keyId}"]`);
    const groupId = keyRow.data('group-id');
    
    if (groupId) {
        showToast('正在检查API密钥...', 'info');
        checkGroupNow(groupId);
    } else {
        showToast('无法找到API密钥所属的组', 'error');
    }
}


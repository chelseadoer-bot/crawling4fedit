import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createBrand,
  waitForCrawl,
  deleteBrand,
  downloadUrl,
  fetchBrands,
  fetchGroupPreview,
  fetchPreview,
  updateBrand,
} from './api'

const ALL_COLUMNS = [
  '이미지', '상품명', '브랜드', '카테고리', '성별',
  '정상가', '판매가', '할인율', '컬러', '소재',
  '사이즈', '핏', '기장', '소매길이', '스타일',
  '안감', '두께감', '계절감', '비침', '신축성',
  '평점', '리뷰수', '상품링크', '수집일시',
]
const IMAGE_COL = '이미지'
const LINK_COL = '상품링크'

const CATEGORY_ORDER = ['SPA', '명품', '신진해외브랜드', '디자이너브랜드', '보세브랜드']
const CATEGORY_LABELS = {
  'SPA': 'SPA',
  '명품': '명품',
  '신진해외브랜드': '신진해외브랜드',
  '디자이너브랜드': '디자이너브랜드',
  '보세브랜드': '보세브랜드',
}

function formatLastCrawled(at) {
  if (!at) return '미수집'
  const m = at.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/)
  if (!m) return at
  return `${m[2]}/${m[3]} ${m[4]}:${m[5]}`
}

function groupSlug(group) {
  return (
    group
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/[\s_]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '') || 'other'
  )
}

// 3단 계층: category → brand groups → items
function buildCategoryTree(brands) {
  const catMap = new Map()

  for (const brand of brands) {
    const cat = brand.category || '기타'
    if (!catMap.has(cat)) catMap.set(cat, new Map())
    const groupMap = catMap.get(cat)
    const grp = brand.group || brand.name
    if (!groupMap.has(grp)) groupMap.set(grp, [])
    groupMap.get(grp).push(brand)
  }

  const result = []
  const seen = new Set()

  for (const cat of CATEGORY_ORDER) {
    if (catMap.has(cat)) {
      seen.add(cat)
      result.push({ category: cat, groups: buildGroupList(catMap.get(cat), cat) })
    }
  }
  for (const [cat, groupMap] of catMap) {
    if (!seen.has(cat)) {
      result.push({ category: cat, groups: buildGroupList(groupMap, cat) })
    }
  }
  return result
}

function buildGroupList(groupMap, categoryName) {
  return [...groupMap.entries()].map(([group, items]) => ({
    group,
    // gid: category+group 조합으로 전역 고유키 보장 (한글 브랜드명도 안전)
    gid: `${categoryName}||${group}`,
    slug: groupSlug(group),  // API 호출용 (영문 브랜드만 의미있음)
    items,
    totalCount: items.reduce((s, b) => s + (b.product_count ?? 0), 0),
    lastCrawled: items.map((b) => b.last_crawled_at).filter(Boolean).sort().pop(),
    hasCrawlable: items.some((b) => b.crawlable),
    enabled: items.some((b) => b.enabled),
  }))
}

function RefreshIcon({ spinning }) {
  return (
    <svg
      className={`icon-refresh${spinning ? ' spinning' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <polyline points="21 3 21 9 15 9" />
    </svg>
  )
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="icon-edit" aria-hidden>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  )
}

export default function App() {
  const [brands, setBrands] = useState([])
  const [selection, setSelection] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [crawlingId, setCrawlingId] = useState(null)
  const [crawlingGroup, setCrawlingGroup] = useState(null)
  const [expandedCats, setExpandedCats] = useState({})
  const [expandedGroups, setExpandedGroups] = useState({})
  const [showAdd, setShowAdd] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [form, setForm] = useState({ group: '', name: '', url: '' })
  const [editForm, setEditForm] = useState({ group: '', name: '', url: '' })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [crawlProgress, setCrawlProgress] = useState('')
  const [dragGroup, setDragGroup] = useState(null)   // 드래그 중인 그룹 {gid, group, items}
  const [dropTarget, setDropTarget] = useState(null)  // 드롭 hover 중인 카테고리명

  const categoryTree = useMemo(() => buildCategoryTree(brands), [brands])

  const selectedBrand =
    selection?.type === 'brand' ? brands.find((b) => b.id === selection.id) : null

  const selectedGroup = useMemo(() => {
    if (selection?.type !== 'group') return null
    for (const catNode of categoryTree) {
      const g = catNode.groups.find((g) => g.gid === selection.gid)
      if (g) return g
    }
    return null
  }, [selection, categoryTree])

  const refresh = useCallback(async (keepSelection = true) => {
    const data = await fetchBrands()
    setBrands(data.brands)
    if (!keepSelection) return
    if (selection?.type === 'brand' && !data.brands.some((b) => b.id === selection.id)) {
      setSelection(null)
    }
  }, [selection])

  const loadPreview = useCallback(async (sel) => {
    if (!sel) { setPreview(null); return }
    try {
      if (sel.type === 'group') {
        const data = await fetchGroupPreview(sel.apiSlug)
        setPreview(data)
      } else {
        const data = await fetchPreview(sel.id)
        setPreview(data)
      }
    } catch {
      setPreview(null)
    }
  }, [])

  useEffect(() => {
    fetchBrands()
      .then((data) => {
        setBrands(data.brands)
        // 모든 카테고리 기본 열기
        const tree = buildCategoryTree(data.brands)
        const cats = {}
        const grps = {}
        for (const catNode of tree) {
          cats[catNode.category] = true
          for (const g of catNode.groups) grps[g.gid] = false // 기본 접힘
        }
        setExpandedCats(cats)
        setExpandedGroups(grps)
        // 첫 번째 enabled 브랜드 자동 선택
        const firstEnabled = data.brands.find((b) => b.enabled && b.has_csv)
        if (firstEnabled) {
          setSelection({ type: 'brand', id: firstEnabled.id })
          const cat = firstEnabled.category || '기타'
          const grpGid = `${cat}||${firstEnabled.group || firstEnabled.name}`
          setExpandedGroups((prev) => ({ ...prev, [grpGid]: true }))
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadPreview(selection)
  }, [selection, loadPreview])

  const openEdit = (brand) => {
    setEditForm({ group: brand.group || '', name: brand.name, url: brand.default_url })
    setShowEdit(true)
    setSelection({ type: 'brand', id: brand.id })
  }

  const handleAddBrand = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const brand = await createBrand(form.name, form.url, form.group)
      setForm({ group: '', name: '', url: '' })
      setShowAdd(false)
      setSelection({ type: 'brand', id: brand.id })
      await refresh(false)
      if (brand.crawlable && brand.crawl_started) {
        setCrawlingId(brand.id)
        setMessage(`「${brand.group} · ${brand.name}」 추가됨 — 크롤링 시작`)
        try {
          const result = await waitForCrawl(brand.id, (job) => {
            setCrawlProgress(job.message || '')
            setMessage(job.message || '수집 중…')
          }, { start: false })
          setMessage(`「${brand.group} · ${brand.name}」 ${result.count}개 수집 완료`)
          await refresh()
          await loadPreview({ type: 'brand', id: brand.id })
        } catch (err) {
          setError(err.message)
        } finally {
          setCrawlingId(null)
          setCrawlProgress('')
        }
      } else if (!brand.crawlable) {
        setMessage(`「${brand.group} · ${brand.name}」 추가됨 (지원하지 않는 사이트)`)
      } else {
        setMessage(`「${brand.group} · ${brand.name}」 추가됨`)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const handleEditBrand = async (e) => {
    e.preventDefault()
    if (!selectedBrand) return
    setError('')
    try {
      const brand = await updateBrand(selectedBrand.id, editForm)
      setShowEdit(false)
      setMessage(`「${brand.group} · ${brand.name}」 수정됨`)
      await refresh()
      await loadPreview({ type: 'brand', id: brand.id })
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async () => {
    if (!selectedBrand || !confirm(`「${selectedBrand.group} · ${selectedBrand.name}」 삭제할까요?`)) return
    setError('')
    try {
      await deleteBrand(selectedBrand.id)
      setMessage('카테고리가 삭제되었습니다.')
      setPreview(null)
      setSelection(null)
      await refresh(false)
    } catch (err) {
      setError(err.message)
    }
  }

  const handleCrawl = async (brandId) => {
    const brand = brands.find((b) => b.id === brandId)
    if (!brand?.crawlable) return
    setError('')
    setMessage('')
    setCrawlProgress('')
    setCrawlingId(brandId)
    try {
      const result = await waitForCrawl(brandId, (job) => {
        setCrawlProgress(job.message || '')
        setMessage(job.message || '수집 중…')
      })
      setMessage(`「${brand.group} · ${brand.name}」 ${result.count}개로 업데이트`)
      await refresh()
      if (selection?.type === 'brand' && selection.id === brandId) await loadPreview(selection)
      else if (selection?.type === 'group') await loadPreview(selection)
    } catch (err) {
      setError(err.message)
    } finally {
      setCrawlingId(null)
      setCrawlProgress('')
    }
  }

  const handleCrawlGroup = async (group) => {
    const crawlable = group.items.filter((b) => b.crawlable)
    if (!crawlable.length) return
    setError('')
    setMessage('')
    setCrawlingGroup(group.gid)
    try {
      let total = 0
      for (const brand of crawlable) {
        setCrawlingId(brand.id)
        const result = await waitForCrawl(brand.id, (job) => {
          setCrawlProgress(job.message || '')
          setMessage(`「${brand.name}」 ${job.message || '수집 중…'}`)
        })
        total += result.count
      }
      setMessage(`「${group.group}」 전체 ${total}개로 업데이트`)
      await refresh()
      if (selection?.type === 'group') await loadPreview({ type: 'group', gid: group.gid, apiSlug: group.slug })
    } catch (err) {
      setError(err.message)
    } finally {
      setCrawlingId(null)
      setCrawlingGroup(null)
    }
  }

  const toggleCat = (cat) => setExpandedCats((prev) => ({ ...prev, [cat]: !prev[cat] }))
  const toggleGroup = (gid) => setExpandedGroups((prev) => ({ ...prev, [gid]: !prev[gid] }))

  // ── 드래그&드롭: 브랜드 그룹 → 카테고리 이동 ──
  const handleDragStart = (e, group) => {
    setDragGroup(group)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragEnd = () => {
    setDragGroup(null)
    setDropTarget(null)
  }

  const handleDragOverCat = (e, cat) => {
    if (!dragGroup) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDropTarget(cat)
  }

  const handleDropOnCat = async (e, targetCat) => {
    e.preventDefault()
    setDropTarget(null)
    if (!dragGroup) return
    // 같은 카테고리면 무시
    const currentCat = dragGroup.items[0]?.category
    if (currentCat === targetCat) { setDragGroup(null); return }

    setError('')
    try {
      await Promise.all(dragGroup.items.map((b) => updateBrand(b.id, { category: targetCat })))
      setMessage(`「${dragGroup.group}」→ ${targetCat} 이동됨`)
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setDragGroup(null)
    }
  }

  if (loading) {
    return <div className="app loading"><div className="spinner" /></div>
  }

  const mainTitle = selectedGroup
    ? selectedGroup.group
    : selectedBrand
      ? `${selectedBrand.group} · ${selectedBrand.name}`
      : ''

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-head">
          <h1>크롤링</h1>
          <button type="button" className="btn-add" onClick={() => setShowAdd(true)}>+</button>
        </div>

        <ul className="brand-list">
          {categoryTree.length === 0 && <li className="brand-empty">브랜드를 추가해주세요</li>}

          {categoryTree.map(({ category, groups }) => {
            const catOpen = expandedCats[category] !== false
            return (
              <li key={category} className="cat-block">
                {/* 대구분 헤더 */}
                <button
                  type="button"
                  className={`cat-header${dropTarget === category ? ' drop-target' : ''}`}
                  onClick={() => toggleCat(category)}
                  onDragOver={(e) => handleDragOverCat(e, category)}
                  onDragLeave={() => setDropTarget(null)}
                  onDrop={(e) => handleDropOnCat(e, category)}
                  aria-expanded={catOpen}
                >
                  <span className="cat-arrow">{catOpen ? '▾' : '▸'}</span>
                  <span className="cat-label">{CATEGORY_LABELS[category] || category}</span>
                  <span className="cat-count">{groups.reduce((s, g) => s + g.totalCount, 0) || ''}</span>
                  {dropTarget === category && <span className="drop-hint">여기에 놓기</span>}
                </button>

                {catOpen && (
                  <ul className="group-list">
                    {groups.map((group) => {
                      const isGroupActive = selection?.type === 'group' && selection.gid === group.gid
                      const isOpen = expandedGroups[group.gid] !== false
                      const hasMultiple = group.items.length > 1

                      return (
                        <li key={group.gid} className="group-block">
                          <div
                            className={`group-head ${isGroupActive ? 'active' : ''} ${!group.enabled ? 'disabled' : ''} ${dragGroup?.gid === group.gid ? 'dragging' : ''}`}
                            draggable
                            onDragStart={(e) => handleDragStart(e, group)}
                            onDragEnd={handleDragEnd}
                          >
                            {hasMultiple && (
                              <button
                                type="button"
                                className="btn-fold"
                                onClick={() => toggleGroup(group.gid)}
                                aria-label={isOpen ? '접기' : '펼치기'}
                              >
                                {isOpen ? '▾' : '▸'}
                              </button>
                            )}
                            <button
                              type="button"
                              className="group-title-btn"
                              onClick={() => {
                                if (hasMultiple) {
                                  setSelection({ type: 'group', gid: group.gid, apiSlug: group.slug })
                                  toggleGroup(group.gid)
                                } else {
                                  setSelection({ type: 'brand', id: group.items[0].id })
                                }
                              }}
                            >
                              <span className="brand-info">
                                <span className="brand-name">{group.group}</span>
                                <span className="brand-last">
                                  {group.enabled ? formatLastCrawled(group.lastCrawled) : '미지원'}
                                </span>
                              </span>
                              <span className="brand-count">{group.totalCount || ''}</span>
                            </button>
                            {group.hasCrawlable && (
                              <button
                                type="button"
                                className="btn-refresh"
                                title="그룹 전체 업데이트"
                                disabled={crawlingGroup === group.gid}
                                onClick={() => handleCrawlGroup(group)}
                              >
                                <RefreshIcon spinning={crawlingGroup === group.gid} />
                              </button>
                            )}
                          </div>

                          {isOpen && hasMultiple && (
                            <ul className="item-list">
                              {group.items.map((brand) => {
                                const isActive = selection?.type === 'brand' && selection.id === brand.id
                                return (
                                  <li key={brand.id} className={`category-row ${isActive ? 'active' : ''} ${!brand.enabled ? 'disabled' : ''}`}>
                                    <button
                                      type="button"
                                      className="category-item"
                                      onClick={() => setSelection({ type: 'brand', id: brand.id })}
                                    >
                                      <span className="brand-info">
                                        <span className="category-name">{brand.name}</span>
                                        <span className="brand-last">
                                          {brand.enabled ? formatLastCrawled(brand.last_crawled_at) : '미지원'}
                                        </span>
                                      </span>
                                      <span className="brand-count sm">{brand.product_count || ''}</span>
                                    </button>
                                    <button type="button" className="btn-icon" title="수정" onClick={() => openEdit(brand)}>
                                      <EditIcon />
                                    </button>
                                    {brand.crawlable && (
                                      <button
                                        type="button"
                                        className="btn-refresh sm"
                                        title="업데이트"
                                        disabled={crawlingId === brand.id}
                                        onClick={() => handleCrawl(brand.id)}
                                      >
                                        <RefreshIcon spinning={crawlingId === brand.id} />
                                      </button>
                                    )}
                                  </li>
                                )
                              })}
                            </ul>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </li>
            )
          })}
        </ul>
      </aside>

      <main className="main">
        {!selection ? (
          <div className="empty-main">
            <p>왼쪽에서 브랜드를 선택하세요.</p>
          </div>
        ) : (
          <>
            <header className="main-head">
              <div>
                <h2>{mainTitle}</h2>
                {selectedBrand && (
                  <a href={selectedBrand.default_url} target="_blank" rel="noreferrer" className="url">
                    {selectedBrand.default_url}
                  </a>
                )}
                {selectedGroup && (
                  <p className="group-sub">
                    {selectedGroup.items.map((b) => b.name).join(' · ')} · 총 {selectedGroup.totalCount}개
                  </p>
                )}
              </div>
              <div className="actions">
                {selectedBrand && (
                  <>
                    <button
                      type="button"
                      className="btn primary with-icon"
                      onClick={() => handleCrawl(selectedBrand.id)}
                      disabled={crawlingId === selectedBrand.id || !selectedBrand.crawlable}
                    >
                      <RefreshIcon spinning={crawlingId === selectedBrand.id} />
                      {crawlingId === selectedBrand.id ? '업데이트 중…' : '업데이트'}
                    </button>
                    {selectedBrand.has_csv && (
                      <a className="btn" href={downloadUrl(selectedBrand.id)} download>CSV</a>
                    )}
                    <button type="button" className="btn" onClick={() => openEdit(selectedBrand)}>수정</button>
                    <button type="button" className="btn ghost" onClick={handleDelete}>삭제</button>
                  </>
                )}
                {selectedGroup && selectedGroup.hasCrawlable && (
                  <button
                    type="button"
                    className="btn primary with-icon"
                    onClick={() => handleCrawlGroup(selectedGroup)}
                    disabled={crawlingGroup === selectedGroup.gid}
                  >
                    <RefreshIcon spinning={crawlingGroup === selectedGroup.slug} />
                    전체 업데이트
                  </button>
                )}
              </div>
            </header>

            {message && <p className="msg success">{message}</p>}
            {crawlProgress && crawlingId && <p className="msg info">{crawlProgress}</p>}
            {error && <p className="msg error">{error}</p>}

            {selectedGroup && preview?.categories && (
              <div className="meta category-chips">
                {preview.categories.map((c) => (
                  <button key={c.id} type="button" className="chip" onClick={() => setSelection({ type: 'brand', id: c.id })}>
                    {c.name} {c.product_count}
                  </button>
                ))}
              </div>
            )}

            {selectedBrand && (
              <div className="meta">
                <span>수집 {selectedBrand.product_count ?? 0}개</span>
                <span>마지막 {selectedBrand.last_crawled_at || '—'}</span>
                {!selectedBrand.enabled && <span className="badge-unsupported">미지원 사이트</span>}
              </div>
            )}

            {selectedGroup && !selectedBrand && (
              <div className="meta">
                <span>전체 {preview?.total_count ?? selectedGroup.totalCount}개</span>
                <span>카테고리 {selectedGroup.items.length}개</span>
              </div>
            )}

            <div className="table-area">
              {!selectedBrand?.enabled ? (
                <div className="table-empty unsupported">
                  아직 크롤러가 지원되지 않는 브랜드입니다.
                </div>
              ) : !preview?.rows?.length ? (
                <div className="table-empty">
                  {crawlingId
                    ? '수집 중입니다…'
                    : preview?.crawl_job?.status === 'running'
                      ? preview.crawl_job.message || '백그라운드에서 수집 중…'
                      : '업데이트(🔄)를 누르면 결과가 여기에 표시됩니다.'}
                </div>
              ) : (() => {
                const visibleCols = ALL_COLUMNS.filter(col =>
                  preview.rows.some(row => row[col] && row[col] !== '—')
                )
                return (
                  <table>
                    <thead>
                      <tr>{visibleCols.map((col) => <th key={col}>{col}</th>)}</tr>
                    </thead>
                    <tbody>
                      {preview.rows.map((row, i) => (
                        <tr key={i}>
                          {visibleCols.map((col) => (
                            <td key={col}>
                              {col === IMAGE_COL && row[col] ? (
                                <img src={row[col]} alt="" className="thumb" loading="lazy" />
                              ) : col === LINK_COL && row[col] ? (
                                <a href={row[col]} target="_blank" rel="noreferrer" className="product-link">링크</a>
                              ) : (
                                row[col] || '—'
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              })()}
            </div>
          </>
        )}
      </main>

      {showAdd && (
        <div className="modal-backdrop" onClick={() => setShowAdd(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleAddBrand}>
            <h3>카테고리 추가</h3>
            <label>
              사이트 (그룹)
              <input value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} placeholder="예: UNIQLO (비우면 URL에서 자동)" />
            </label>
            <label>
              카테고리명
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="예: 여성 상의" required />
            </label>
            <label>
              크롤링 URL
              <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://www.uniqlo.com/kr/ko/women/tops" required />
            </label>
            <p className="form-hint">
              ZARA · UNIQLO · H&M · COS · THE BARNNET · DIOR · CHANEL · MONCLER · BALENCIAGA URL은 추가 후 자동 크롤링됩니다.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setShowAdd(false)}>취소</button>
              <button type="submit" className="btn primary">추가</button>
            </div>
          </form>
        </div>
      )}

      {showEdit && selectedBrand && (
        <div className="modal-backdrop" onClick={() => setShowEdit(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleEditBrand}>
            <h3>카테고리 수정</h3>
            <label>
              사이트 (그룹)
              <input value={editForm.group} onChange={(e) => setEditForm({ ...editForm, group: e.target.value })} required />
            </label>
            <label>
              카테고리명
              <input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} required />
            </label>
            <label>
              크롤링 URL
              <input value={editForm.url} onChange={(e) => setEditForm({ ...editForm, url: e.target.value })} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setShowEdit(false)}>취소</button>
              <button type="submit" className="btn primary">저장</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}

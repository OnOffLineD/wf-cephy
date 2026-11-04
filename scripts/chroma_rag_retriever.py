import os
import json
import re
from typing import Dict, Any, Optional, List
try:
    import chromadb
except ImportError:
    chromadb = None
from scripts.wf_data_indexer import WFDataIndexer
from scripts.path_config import get_path

class FastEmbeddingFunction:
    def __call__(self, input: Any) -> Any:
        return [[0.0] * 8 for _ in input]

    def name(self) -> str:
        return "default"

class ChromaRAGRetriever:
    def __init__(self, db_path: str = 'data/chroma_db', data_dir: str = 'data/raw_wfcd', wiki_dir: str = 'rules/wiki_docs'):
        self.data_dir = get_path(data_dir) if not os.path.isabs(data_dir) else data_dir
        self.wiki_dir = get_path(wiki_dir) if not os.path.isabs(wiki_dir) else wiki_dir
        self.db_path = get_path(db_path) if not os.path.isabs(db_path) else db_path
        self.indexer = WFDataIndexer(data_dir=self.data_dir)
        self.documents: List[Dict[str, Any]] = []
        self._last_manifest: Dict[str, float] = {}
        self._indexed = False
        self.client = None
        self.collection = None
        self.build_index()

    def build_index(self, force_rebuild: bool = False):
            docs = []
            ids = []
            metadatas = []

            # Initialize _last_manifest and _indexed if not already set
            self._last_manifest = getattr(self, '_last_manifest', {})
            self._indexed = getattr(self, '_indexed', False)

            # Compute manifest for current files
            manifest = {}
            if os.path.exists(self.wiki_dir):
                for root, _, files in os.walk(self.wiki_dir):
                    for file in files:
                        if file.endswith(('.md', '.txt')):
                            file_path = os.path.join(root, file)
                            manifest[file] = os.path.getmtime(file_path)

            # Check if rebuild is necessary
            if not force_rebuild and self._indexed and manifest == self._last_manifest:
                return

            # 1. Index Wiki Docs
            for root, _, files in os.walk(self.wiki_dir):
                for file in files:
                    if file.endswith(('.md', '.txt')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                        except Exception:
                            continue

                        # Extract the first '# ' line as doc_title
                        doc_title_match = re.search(r'^# (.+)', content, flags=re.MULTILINE)
                        doc_title = doc_title_match.group(1).strip() if doc_title_match else file

                        # Split by markdown headers
                        sections = re.split(r'^(#{1,3} .+|==+ .+ ==+)', content, flags=re.MULTILINE)
                        sections = [s.strip() for s in sections if s and s.strip()]

                        current_header = "Whole Document"
                        for idx, section in enumerate(sections):
                            if section.startswith('#') or section.startswith('=='):
                                current_header = section
                            else:
                                chunk_id = f"wiki_{file}_{idx}"
                                if len(section) > 1200:
                                    sub_chunks = [section[i:i+1200] for i in range(0, len(section), 1200)]
                                    for sub_idx, sub_chunk in enumerate(sub_chunks):
                                        sub_chunk_id = f"{chunk_id}_sub_{sub_idx}"
                                        docs.append(sub_chunk)
                                        ids.append(sub_chunk_id)
                                        metadatas.append({
                                            "id": sub_chunk_id,
                                            "title": f'{doc_title} ({file})',
                                            "section": current_header,
                                            "text": sub_chunk,
                                            "source": "wiki"
                                        })
                                else:
                                    docs.append(section)
                                    ids.append(chunk_id)
                                    metadatas.append({
                                        "id": chunk_id,
                                        "title": f'{doc_title} ({file})',
                                        "section": current_header,
                                        "text": section,
                                        "source": "wiki"
                                    })

            # 2. Index Relics
            relics_path = os.path.join(self.data_dir, 'Relics.json')
            if os.path.exists(relics_path):
                try:
                    with open(relics_path, 'r', encoding='utf-8') as f:
                        relics_data = json.load(f)
                        for idx, r in enumerate(relics_data):
                            name = r.get('name', '')
                            vaulted_str = "단종됨" if r.get('vaulted') else "획득가능"
                            rewards = [f"{item.get('item')} ({item.get('type')})" for item in r.get('rewards', [])]
                            summary = f"[성유물] {name} ({vaulted_str})\n드랍 보상 목록: {', '.join(rewards)}"
                            chunk_id = f"relic_{name.replace(' ', '_')}_{idx}"
                            docs.append(summary)
                            ids.append(chunk_id)
                            metadatas.append({
                                "id": chunk_id,
                                "title": name,
                                "section": "Relics",
                                "text": summary,
                                "source": "relic"
                            })
                except Exception:
                    pass

            # 3. Index Sortie Rewards & Drops
            drops_path = os.path.join(self.data_dir, 'drops_all.json')
            if os.path.exists(drops_path):
                try:
                    with open(drops_path, 'r', encoding='utf-8') as f:
                        drops_data = json.load(f)
                        sortie = drops_data.get('sortieRewards', [])
                        if sortie:
                            rewards_summary = []
                            for item in sortie:
                                rewards_summary.append(f"{item.get('itemName')} (확률: {item.get('chance')}%)")
                            summary = "[출격(Sortie) 공식 보상 테이블]\n" + "\n".join(rewards_summary)
                            chunk_id = "drop_sortie_rewards"
                            docs.append(summary)
                            ids.append(chunk_id)
                            metadatas.append({
                                "id": chunk_id,
                                "title": "Sortie Rewards",
                                "section": "Sortie",
                                "text": summary,
                                "source": "sortie_table"
                            })
                except Exception:
                    pass

            # 4. Batch add to ChromaDB
            batch_size = 100
            for i in range(0, len(docs), batch_size):
                batch_docs = docs[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                batch_metas = metadatas[i:i+batch_size]
                if self.collection:
                    self.collection.upsert(
                        documents=batch_docs,
                        ids=batch_ids,
                        metadatas=batch_metas
                    )

            # Update manifest and indexed status
            self.documents = metadatas
            self._last_manifest = manifest
            self._indexed = True

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
            chunks = []

            # 1. Ensure the index is up-to-date
            self.build_index(force_rebuild=False)

            # 2. Tokenize query and remove particles and stopwords
            query_terms = re.findall(r'[가-힣a-zA-Z0-9]{2,}', query.lower())
            query_terms = [re.sub(r'(은|는|이|가|을|를|에서|에|의|으로|로|와|과|도|만)$', '', term) for term in query_terms]
            stopwords = ['어떻게', '알려줘', '뭐야', '공략', '추천', '방법', '질문', '워프레임', '설명', '미션', '팁']
            query_terms = [t for t in query_terms if len(t) >= 2 and t not in stopwords]
            # Players say 샤드/아콘, while the wiki docs say 집정관.
            if any(t in ('샤드', '아콘', '파편') for t in query_terms) and '집정관' not in query_terms:
                query_terms.append('집정관')

            # 3. Weapon or Warframe name boost. Longer word runs first, so "글레이브 프라임" beats "글레이브".
            word_runs = [''.join(query_terms[i:i + size]) for size in (3, 2, 1) for i in range(len(query_terms) - size + 1)]
            matched_w = next((m for m in map(self.indexer.match_weapon_strict, word_runs) if m), None)
            if matched_w:
                kr_name = matched_w.get('kr_name', '')
                name_display = f"{matched_w['name']} ({kr_name})" if kr_name else matched_w['name']
                if matched_w.get('category') == 'Warframe':
                    title = f"워프레임 스펙: {name_display}"
                    w_card = (
                        f"### [공식 워프레임 팩트 카드: {name_display}]\n"
                        f"- 체력: {matched_w.get('health')}\n"
                        f"- 실드: {matched_w.get('shield')}\n"
                        f"- 방어력: {matched_w.get('armor')}\n"
                        f"- 에너지: {matched_w.get('energy')}"
                    )
                else:
                    crit_pct = round(float(matched_w.get('crit_chance', 0)) * 100, 1)
                    crit_mult = round(float(matched_w.get('crit_mult', 0)), 1)
                    status_pct = round(float(matched_w.get('status_chance', 0)) * 100, 1)
                    title = f"무기 스펙: {name_display}"
                    w_card = (
                        f"### [공식 무기 팩트 카드: {name_display}]\n"
                        f"- 분류: {matched_w.get('category')}\n"
                        f"- 기본 피해량: {matched_w.get('total_damage')}\n"
                        f"- 치명타 확률: {crit_pct}%\n"
                        f"- 치명타 배수: {crit_mult}x\n"
                        f"- 연사력: {matched_w.get('fire_rate')}\n"
                        f"- 상태이상 확률: {status_pct}%"
                    )
                chunks.append({
                    "type": "weapon_spec",
                    "title": title,
                    "section": "팩트 카드",
                    "text": w_card,
                    "score": 25.0
                })

            # 4. Score documents in self.documents
            q_raw = query.lower()
            for doc in self.documents:
                score = 0.0
                title = (doc.get('title') or '').lower()
                section = (doc.get('section') or '').lower()
                text = (doc.get('text') or '').lower()

                for term in query_terms:
                    if len(term) >= 2:
                        # Highest priority to exact section header match (with specific logic for '방어' and '생존')
                        if term in section:
                            if term == '방어' and '이동' not in q_raw and '이동방어' in section:
                                score += 2.0
                            elif term == '방어' and '이동방어' not in section:
                                score += 18.0
                            elif term == '생존' and '미션' in q_raw and '생존 미션' in section:
                                score += 25.0
                            elif term == '생존' and '미션' in q_raw and ('실드' in section or '게이팅' in section or 'shield' in section.lower()):
                                score += 1.0
                            else:
                                score += 18.0
                        if term in title:
                            score += 2.0
                        if term in text:
                            score += 1.0

                if score > 0:
                    chunks.append({
                        "type": doc.get('source', 'wiki'),
                        "title": doc.get('title', ''),
                        "section": doc.get('section', ''),
                        "text": doc.get('text', ''),
                        "score": score
                    })

            # 5. Deduplicate chunks by (title, section, text) and sort
            seen = set()
            deduplicated_chunks = []
            for chunk in chunks:
                # Use a tuple of key identifying features for deduplication
                key = (chunk.get('title', ''), chunk.get('section', ''), chunk.get('text', ''))
                if key not in seen:
                    seen.add(key)
                    deduplicated_chunks.append(chunk)

            # Sort chunks by score in descending order
            deduplicated_chunks.sort(key=lambda x: x.get('score', 0), reverse=True)

            # Return top_k ranked results
            return deduplicated_chunks[:top_k]


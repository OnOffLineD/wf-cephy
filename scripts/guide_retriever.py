"""Guide search: character n-gram BM25 over rules/wiki_docs, plus weapon and warframe fact cards."""
import json
import math
import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from scripts.path_config import get_path
from scripts.wf_data_indexer import WFDataIndexer

BM25_K1 = 1.2
BM25_B = 0.75
TITLE_BOOST = 3
SECTION_BOOST = 4
# A doc titled after a word in the question is about that subject, not just mentioning it.
TITLE_SUBJECT_BONUS = 1.5
MAX_CHUNK_CHARS = 1200
# Share of the question's important words a chunk must contain to count as an answer.
MIN_COVERAGE = 0.6
MIN_WORD_GRAM_MATCH = 0.6

# Question wording that says nothing about the topic.
FILLER_WORDS = {
    '어떻게', '어케', '어떡해', '알려줘', '알려', '알려주', '뭐야', '뭔가', '뭐', '뭘', '뭘로', '뭐로', '뭐부터', '뭐있어', '무슨', '어떤',
    '어디', '어디서', '어디야', '어디가', '어딨어', '언제', '왜', '누구', '얼마', '몇', '좋아', '좋은', '좋을까', '좋아요', '가는게',
    '잡아', '잡아야', '잡아야돼', '잡는', '잡는법', '잡으면', '깨', '깨는', '깨는법', '풀어', '푸는', '해', '하는', '하는법', '해야', '해야돼', '해야해',
    '법', '방법', '써', '쓰는', '구해', '얻어', '얻는', '나와', '나오는', '떨궈', '들고가', '있어', '돼', '되는', '줘', '좀', '좋', '찾는', '찾아',
    '만들어', '만드는', '버는', '막혔어', '막혀', '구분해', '준비해', '띄워', '거기서', '거긴', '거기는', '그거', '이거', '진짜', '빨리', '이번주', '오늘', '전에',
    '인데', '까는게', '지어', '사', '는법',
}
# Topic-free words that help ranking ("생존 미션") but should not decide whether a chunk answers.
WEAK_WORDS = {'공략', '추천', '미션', '팁', '설명', '워프레임', '가이드', '정보', '질문', '수단', '종류', '시작', '패턴', '속성'}
PARTICLE = re.compile(r'(한테|에게|에서|으로|이랑|부터|까지|인데|이야|은|는|이|가|을|를|에|의|로|와|과|도|만|랑|야)$')
# These ask about the item itself, so its card outranks any guide text.
SPEC_QUESTION = re.compile(r'스펙|공략|정보|체력|실드|방어력|에너지|치명|치확|연사|빌드')


def _compact(text: str) -> str:
    return re.sub(r'[^0-9a-z가-힣]', '', text.lower())


def _grams(text: str, sizes: Tuple[int, ...] = (2, 3)) -> List[str]:
    """Spaces are dropped first, so "두번째 꿈" and "두 번째 꿈" share every piece."""
    compact = _compact(text)
    return [compact[i:i + n] for n in sizes for i in range(len(compact) - n + 1)]


def _strip_particle(word: str) -> str:
    stripped = PARTICLE.sub('', word)
    return stripped if len(stripped) >= 2 else word


def _split_long_section(section: str) -> List[str]:
    """Cut at line ends so an answer never starts mid sentence."""
    if len(section) <= MAX_CHUNK_CHARS:
        return [section]
    pieces, current = [], ''
    for line in section.splitlines():
        if current and len(current) + len(line) > MAX_CHUNK_CHARS:
            pieces.append(current.strip())
            current = ''
        current += line + '\n'
    if current.strip():
        pieces.append(current.strip())
    return [p[i:i + MAX_CHUNK_CHARS] for p in pieces for i in range(0, len(p), MAX_CHUNK_CHARS)]


class GuideRetriever:
    def __init__(self, data_dir: str = 'data/raw_wfcd', wiki_dir: str = 'rules/wiki_docs', aliases_path: str = 'data/guide_aliases.json'):
        self.data_dir = get_path(data_dir) if not os.path.isabs(data_dir) else data_dir
        self.wiki_dir = get_path(wiki_dir) if not os.path.isabs(wiki_dir) else wiki_dir
        self.indexer = WFDataIndexer(data_dir=self.data_dir)
        self.phrase_aliases, self.word_aliases = self._load_aliases(get_path(aliases_path) if not os.path.isabs(aliases_path) else aliases_path)
        self.documents: List[Dict[str, Any]] = []
        self._postings: Dict[str, Dict[int, float]] = {}
        self._doc_lengths: List[float] = []
        self._doc_grams: List[set] = []
        self._avg_length = 1.0
        self._last_manifest: Dict[str, float] = {}
        self._indexed = False
        self.build_index()

    @staticmethod
    def _load_aliases(path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}, {}
        return data.get('phrases', {}), data.get('words', {})

    def _wiki_files(self) -> List[str]:
        return [os.path.join(root, f) for root, _, files in os.walk(self.wiki_dir) for f in files if f.endswith(('.md', '.txt'))]

    def _wiki_chunks(self, paths: List[str]) -> List[Dict[str, Any]]:
        chunks = []
        for path in paths:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except OSError:
                continue
            file_name = os.path.basename(path)
            title_match = re.search(r'^# (.+)', content, flags=re.MULTILINE)
            doc_title = title_match.group(1).strip() if title_match else file_name
            header = 'Whole Document'
            for part in re.split(r'^(#{1,3} .+|==+ .+ ==+)', content, flags=re.MULTILINE):
                part = part.strip()
                if not part:
                    continue
                if part.startswith(('#', '==')):
                    header = part
                    continue
                for piece in _split_long_section(part):
                    chunks.append({'title': f'{doc_title} ({file_name})', 'doc_title': doc_title, 'section': header, 'text': piece, 'source': 'wiki'})
        return chunks

    def _sortie_chunk(self) -> List[Dict[str, Any]]:
        try:
            with open(os.path.join(self.data_dir, 'drops_all.json'), 'r', encoding='utf-8') as f:
                sortie = json.load(f).get('sortieRewards', [])
        except (OSError, ValueError):
            return []
        if not sortie:
            return []
        rewards = "\n".join(f"{item.get('itemName')} (확률: {item.get('chance')}%)" for item in sortie)
        return [{'title': '출격 보상 테이블', 'doc_title': '출격 보상 테이블', 'section': 'Sortie', 'text': f"[출격(Sortie) 공식 보상 테이블]\n{rewards}", 'source': 'sortie_table'}]

    def build_index(self, force_rebuild: bool = False):
        paths = self._wiki_files()
        manifest = {p: os.path.getmtime(p) for p in paths}
        if not force_rebuild and self._indexed and manifest == self._last_manifest:
            return

        documents = self._wiki_chunks(paths) + self._sortie_chunk()
        postings: Dict[str, Dict[int, float]] = defaultdict(dict)
        lengths, gram_sets = [], []
        for idx, doc in enumerate(documents):
            counts = Counter(_grams(doc['text']))
            for gram in _grams(doc['doc_title']):
                counts[gram] += TITLE_BOOST
            for gram in _grams(doc['section']):
                counts[gram] += SECTION_BOOST
            for gram, count in counts.items():
                postings[gram][idx] = count
            lengths.append(sum(counts.values()))
            gram_sets.append(set(counts))

        self.documents = documents
        self._postings = dict(postings)
        self._doc_lengths = lengths
        self._doc_grams = gram_sets
        self._avg_length = (sum(lengths) / len(lengths)) if lengths else 1.0
        self._last_manifest = manifest
        self._indexed = True

    def _idf(self, gram: str) -> float:
        df = len(self._postings.get(gram, ()))
        return math.log(1 + (len(self.documents) - df + 0.5) / (df + 0.5))

    def _query_words(self, query: str) -> Tuple[List[str], List[str]]:
        """Returns the topic words a chunk must cover, and every kept word in question order for phrase matching."""
        text = query.lower()
        for phrase, official in self.phrase_aliases.items():
            text = text.replace(phrase, f' {official} ')

        required, ordered = [], []
        for raw in re.findall(r'[가-힣a-z0-9]+', text):
            stem = _strip_particle(raw)
            if raw in FILLER_WORDS or stem in FILLER_WORDS:
                continue
            for word in self.word_aliases.get(stem, stem).split():
                word = _strip_particle(word)
                ordered.append(word)
                if word not in WEAK_WORDS and len(word) >= 2 and word not in required:
                    required.append(word)
        return required, ordered

    def _coverage(self, words: List[str], doc_idx: int) -> float:
        total = found = 0.0
        for word in words:
            pieces = _grams(word, (2,))
            weight = sum(self._idf(g) for g in pieces) / len(pieces)
            total += weight
            if sum(g in self._doc_grams[doc_idx] for g in pieces) / len(pieces) >= MIN_WORD_GRAM_MATCH:
                found += weight
        return found / total if total else 0.0

    def _search_docs(self, required: List[str], ordered: List[str]) -> List[Dict[str, Any]]:
        if not required:
            return []
        query_grams = set(_grams(''.join(ordered)))
        for word in ordered:
            query_grams.update(_grams(word))

        scores: Dict[int, float] = defaultdict(float)
        for gram in query_grams:
            idf = self._idf(gram)
            for idx, tf in self._postings.get(gram, {}).items():
                norm = 1 - BM25_B + BM25_B * self._doc_lengths[idx] / self._avg_length
                scores[idx] += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * norm)

        hits = []
        for idx, score in scores.items():
            coverage = self._coverage(required, idx)
            if coverage < MIN_COVERAGE:
                continue
            doc = self.documents[idx]
            title_text = _compact(doc['doc_title'])
            if any(word in title_text for word in required):
                score *= TITLE_SUBJECT_BONUS
            hits.append({'type': doc['source'], 'title': doc['title'], 'doc_title': doc['doc_title'], 'section': doc['section'], 'text': doc['text'], 'score': round(score * coverage, 3)})
        hits.sort(key=lambda h: h['score'], reverse=True)
        return hits

    def _fact_card(self, required: List[str]) -> Dict[str, Any]:
        # Longer word runs first, so "글레이브 프라임" beats "글레이브".
        word_runs = [''.join(required[i:i + size]) for size in (3, 2, 1) for i in range(len(required) - size + 1)]
        meta = next((m for m in map(self.indexer.match_weapon_strict, word_runs) if m), None)
        if not meta:
            return {}
        kr_name = meta.get('kr_name', '')
        name_display = f"{meta['name']} ({kr_name})" if kr_name else meta['name']
        if meta.get('category') == 'Warframe':
            title = f"워프레임 스펙: {name_display}"
            card = (
                f"### [공식 워프레임 팩트 카드: {name_display}]\n"
                f"- 체력: {meta.get('health')}\n"
                f"- 실드: {meta.get('shield')}\n"
                f"- 방어력: {meta.get('armor')}\n"
                f"- 에너지: {meta.get('energy')}"
            )
        else:
            title = f"무기 스펙: {name_display}"
            card = (
                f"### [공식 무기 팩트 카드: {name_display}]\n"
                f"- 분류: {meta.get('category')}\n"
                f"- 기본 피해량: {meta.get('total_damage')}\n"
                f"- 치명타 확률: {round(float(meta.get('crit_chance', 0)) * 100, 1)}%\n"
                f"- 치명타 배수: {round(float(meta.get('crit_mult', 0)), 1)}x\n"
                f"- 연사력: {meta.get('fire_rate')}\n"
                f"- 상태이상 확률: {round(float(meta.get('status_chance', 0)) * 100, 1)}%"
            )
        return {'type': 'weapon_spec', 'title': title, 'doc_title': title, 'section': '팩트 카드', 'text': card}

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Returns only chunks that cover the question, so an empty list means the docs do not answer it."""
        self.build_index(force_rebuild=False)
        required, ordered = self._query_words(query)
        hits = self._search_docs(required, ordered)

        card = self._fact_card(required)
        if card:
            top = hits[0]['score'] if hits else 0.0
            if SPEC_QUESTION.search(query) or not hits:
                hits.insert(0, {**card, 'score': top + 1.0})
            else:
                hits.insert(1, {**card, 'score': hits[0]['score']})
        return hits[:top_k]

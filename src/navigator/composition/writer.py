"""Card writer (M3.3.1): the second step of composition.

Why a separate step. In M3.2–M3.3 one model call selected the cards AND wrote every user-facing field.
The language guide was one block in a long selection prompt, the only description of the source was the
corpus card's academic wording («способ участия в действии», «не имеет единственного смысла»,
«любовь не доказывает правильность реакции»), and the model stayed close to that wording to be faithful;
the expandable fields came last in a long JSON and got the least care. Retries re-ran the whole call.

Now the selector (composer.py) only chooses cards and states each distinction; this writer turns ONE chosen
card into the user-facing text, with the reference voice as its main instruction, one call per card, run in
parallel. Every field — title, source explanation, application, question to self, «Что имеется в виду?» and
«Подробнее» — goes through the same prompt, the same contract (``Perspective``) and the same checks. A card
that fails is rewritten alone, with the reason as feedback.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from pydantic import ValidationError

from navigator.composition.references import display_label, fragment_reference
from navigator.language import (
    LANGUAGE_RULES,
    ambiguous_second_question,
    anchor_shift_hits,
    author_simulation_hits,
    gendered_first_person_hits,
    invented_horizon_hits,
    is_open_formulation,
    person_gender,
    stem_hits,
    quote_work_titles,
    retold_sentences,
    false_precision_hits,
    reference_voice_block,
    unnamed_person_claims,
)
from navigator.models.composition import Perspective, meta_hits, word_count
from navigator.models.fragment import Fragment
from navigator.models.interpretation import (
    AMPLIFICATION_RULE,
    INTERNAL_CLAIM_RULE,
    PSYCH_FUNCTION_RULE,
    amplification_hits,
)
from navigator.timing import cli_error_message, cli_usage

WRITER_PROMPT_VERSION = "card-writer-prompt/0.7.0"  # M3.4.2: independently validated; open questions, no invented horizons
USER_FIELDS = ("title", "main_idea", "applied_insight", "reflection_question", "question_explanation", "perspective")
PERSON_FIELDS = ("applied_insight", "reflection_question", "question_explanation")  # speak to the person

WRITER_PROMPT = f"""Ты пишешь ОДНУ карточку философского навигатора для обычного человека. Карточку уже выбрали: известно, какой источник и какое различение она даёт. Твоя задача — рассказать это живым русским языком, так, как умный друг рассказал бы вслух за столом. Сложной может быть мысль, но не язык.

{reference_voice_block()}

Как устроена карточка (как в эталонах):
- title: заголовок-вывод, одно повествовательное предложение (НЕ вопрос), до 9 слов, само различение обычными словами. По форме как «Признать, что не справляешься, ещё не значит сдаться», «Нехватка не обязательно означает поражение».
- main_idea: что говорит или делает источник — 1–3 коротких предложения, ВСЕГО не больше 35 слов, с именем героя, автора или книги. Здесь ещё нет человека.
- applied_insight: что это позволяет увидеть в вопросе человека — 1–3 коротких предложения, ВСЕГО не больше 45 слов. Обычно начинается с его слов («Вы спрашиваете…», «Вы пишете…», «Вы выбираете…») и заканчивается ясным различением. ЗДЕСЬ человек уже получает новую мысль о своём вопросе — «эффект_перспективы» из данных. Проверка: если убрать вопрос к себе, остаётся ли у человека новое понимание? Если нет — карточка слабая, перепиши application.
- reflection_question: вопрос к себе от первого лица — один вопрос, два коротких связанных вопроса или вопрос и короткое уточнение, всего не больше 25 слов. Он ПРОДОЛЖАЕТ мысль application, а не несёт всю ценность карточки вместо неё. Конкретный, о делах, поступках, днях, словах; не философская загадка, не совет.
- question_explanation («Что имеется в виду?»): ПОЯСНЕНИЕ для того, кому мысль карточки показалась непонятной. 1–2 очень простых предложения без вопросительных знаков, ВСЕГО не больше 30 слов: что значит мысль карточки и о чём вопрос к себе. Можно обезличенный пример. Не отвечай за человека, не давай совет.
- perspective («Подробнее»): УГЛУБЛЕНИЕ для того, кому интересно, почему из источника вообще следует такая мысль. Покажи ход рассуждения источника (из «ход_текста» и описания в корпусе): от чего он отталкивается, что с чем связывает и почему из этого возникает различение. Не пересказывай main_idea и applied_insight и не повторяй их предложения; не повторяй «Что имеется в виду?». Можно закончить одним предложением о связи с вопросом. Обычно 30–90 слов; если данных карточки мало — пиши КОРОЧЕ, длина ради длины не нужна. Никаких новых фактов об источнике, советов, биографии и сюжетных подробностей.
- Карточка может работать с одной важной частью вопроса. Не притягивай в конце остальные части вопроса, если источник не даёт для них сильного различения: одна точная перспектива лучше универсальной карточки обо всём.
Любое предложение — не длиннее 20 слов. Эти пределы проверяются автоматически: превышение — ответ отклонят.
ВСЕ шесть полей пишутся одним и тем же живым языком. Раскрываемые блоки («Что имеется в виду?», «Подробнее») — не место для учёного стиля.

{LANGUAGE_RULES}

Метод — сделай это для КАЖДОГО предложения каждого поля, прежде чем ответить:
1. Произнеси предложение вслух. Сказал бы так живой человек? Если это звучит как комментарий, пересказ статьи, перевод с английского или попытка звучать глубоко — перепиши.
2. Если в предложении есть конструкция, которую надо расшифровывать, скажи прямо: кто что делает, говорит, замечает. Примеры из ручной проверки — плохо → в какую сторону:
   - «У Моисея есть третий ход» → «Моисей поступает по-другому: …»
   - «нехватка не имеет одного-единственного смысла» → «нехватка не обязательно означает поражение»
   - «важно, как он участвует в том, что делает» → «важно, с каким настроем он делает то, что делает»
   - «любовь сама не делает реакцию верной», «верная помощь» → «когда близкому плохо, хочется сразу что-то сделать; но не всякое действие ему помогает»
   - «быть в происходящем», «участвовать всерьёз», «каким вы бываете рядом», «быть не там, где нужно» → что человек конкретно делает, говорит, замечает.
   Это направления, а не шаблоны: не вставляй эти фразы туда, где они не по смыслу.
3. Местоимения: у каждого «он, она, оно, они, его, её, в нём, в ней, это, там, так» есть очевидный предмет в том же предложении или прямо перед ним В ЭТОМ ЖЕ поле. Во втором вопросе к себе не ссылайся местоимением на первый — назови предмет снова («Что в этом деле можно устроить иначе?», а не «Что в нём…?»).
4. Описание источника в корпусе дано, чтобы ты не исказил мысль. Оно написано учёным языком — НЕ переноси оттуда слова и обороты. Перескажи мысль своими словами.
5. Источник пересказывай, а не цитируй. Если в данных есть «проверенная_дословная_цитата» — это настоящий текст источника: на него можно опираться как на основание (source_fact), но не вставляй цитату в текст карточки — она показывается человеку отдельно. Если её нет — проверенного текста источника у нас нет. Не пиши «в 22-й главе говорится», не называй номера глав, стихов, аятов, параграфов (ссылка показывается отдельно), не бери слова источника в кавычки как цитату. Хорошо: «В Дао дэ цзин есть мысль…», «Моисей в какой-то момент прямо говорит…», «Эпиктет считает…», «Для Бхагавад-гиты…».
6. О человеке — только то, что он сам сказал (его слова даны). Не добавляй чувств, которых он не называл (сказал «стыдно» — не пиши «боитесь»), не пиши о его любви, мотивах, потребностях, самооценке, биографии; не упоминай врачей, психологов и других специалистов, если он сам о них не писал. {AMPLIFICATION_RULE} {PSYCH_FUNCTION_RULE} {INTERNAL_CLAIM_RULE}
7. Об источнике — только то, что есть в данных карточки (блок «источник»: описание в корпусе и ход текста; «пересказ_отбора» — лишь подсказка к смыслу, не основание). НЕ добавляй сюжетных подробностей, имён, событий, реплик и деталей, которых там нет, даже если ты их помнишь (например, кто ещё был рядом, что именно ответил Бог или учитель). У нас нет проверенного текста источника, и лишняя подробность создаёт ложную видимость, будто мы его прочитали. Если данных мало — скажи мысль короче, не достраивай.
8. Смысл карточки — заданное различение. Не меняй его, не добавляй новую мысль, не давай советов («вам следует…», «вам нужно…»). Карточка остаётся философской: источник виден, это не общий психологический совет.
9. Связь и сочетаемость. Союз показывает настоящую логическую связь («можно много работать, но оставаться спокойным», а не «и оставаться», если это противопоставление). Слова должны естественно сочетаться по-русски: о вещах не говорят, что они «кажутся слабыми», — скажи, что уступчивое, мягкое, гибкое уцелевает.
10. Опорные слова человека. Не заменяй его ключевые слова близкими, если меняется смысл: «принять» ≠ «смириться», «тревога» ≠ «страх», «остановиться» ≠ «сдаться». Дословно переписывать всю его формулировку не нужно — сохраняй смысл.
12. Род. Если в данных «род_человека» = «неизвестен», пиши о человеке без форм, зависящих от рода: не «я готов», «я решил», «я должна», а перестрой фразу («С какой из этих потерь мне было бы легче жить?», «Что мне уже удалось…», «Что мне сейчас важнее…»). Никаких «готов(а)». Если род известен из его слов — пиши в этом роде.
13. Метафора источника. Образ источника (еда, путь, сосуд, ноша…) может объяснять его мысль в main_idea и «Подробнее». В applied_insight, reflection_question и «Что имеется в виду?» переноси РАЗЛИЧЕНИЕ, а не лексику образа: не «работа мне по вкусу», если источник сравнивал с едой. Перечисли слова-образы источника во внутреннем поле metaphor_words — код проверит, что они не протянуты на ситуацию человека.
14. Вопрос к себе проверяет гипотезу открыто. Если применение вводит философскую гипотезу, которой нет в словах человека, вопрос к себе не исходит из того, что она верна, и не подсовывает её как один из заранее заданных вариантов («За поступки мне стыдно или за то, что у меня нет прежнего места?» — нельзя, если человек уже сказал, что не виноват). Лучше открыто: «Что именно становится стыдным, когда я представляю этот разговор?»
15. Без придуманной конкретики. Не вводи сроки и горизонты («через год», «через месяц», «на следующей неделе»), сцены, числа и поведение, которых нет в словах человека, если различение источника не требует именно этого. Можно открыто: «что меняется, если смотреть не только на начало, но и на последствия?»
16. Источник даёт мысль, применяет её система. Не пиши, что автор «предложил бы», «сказал бы вам», «посоветовал бы» что-то современному человеку. Пиши: «Это различение позволяет спросить…» или естественный эквивалент.
17. Не предписывай, как человеку чувствовать или переживать: не «можно спокойно разбираться», «без страха», «честно признать», «правильно отнестись», если это указание на правильный способ чувствовать. Слово само по себе не запрещено — важна его функция в предложении.
18. «Кто я» — особо строго. Не отвечай за человека, кто он и что было «ролью», а что «им самим»: не «потерять место не значит потерять себя», не «работа была ролью, а не частью вас», не «разбираться, что было им самим» так, будто граница известна. Различение оставь предметом его исследования.
Карточку после тебя проверит независимый проверяющий: он читает все шесть полей и сравнивает их со словами человека и материалом источника, не глядя на твой разбор.
11. Названия произведений в связном тексте пиши в кавычках-ёлочках: «Бхагавад-гита», в «Бхагавад-гите», «Дао дэ цзин», «Беседы» Эпиктета, «Письмо к Менекею». Это не цитата. Священные книги (Библия, Ветхий и Новый Завет, Евангелие, Коран, Тора) в кавычки не берутся.

ПРОИСХОЖДЕНИЕ КАЖДОГО УТВЕРЖДЕНИЯ — главное правило (касается всех шести полей, особенно «Что имеется в виду?» и «Подробнее»).
Философия может дать человеку новый взгляд на ИЗВЕСТНЫЕ факты. Она не даёт права создавать новые факты о человеке или о других людях из его рассказа.
Путь: источник → различение → применение к фактам, которые человек САМ сообщил → новый вопрос.
Запрещено: источник → различение → догадка о живом человеке → догадка подана как правда.
Перед ответом разбери каждое утверждение, которое ты пишешь о человеке, о другом человеке из его рассказа (ребёнок, ученик, друг) или об источнике, — к какому виду оно относится:
- user_fact — это сказал или выбрал сам человек (его слова даны). Его собственные слова — не домысел, их можно и нужно использовать.
- source_fact — это есть в данных карточки (описание в корпусе, ход текста). Знание об источнике из твоей памяти сюда не относится: «Эпикур писал о том, как жить без тревоги», «Лао-цзы часто говорит…» без основания в данных — нельзя, даже если это исторически верно. Слова «часто», «всегда», «вся книга», «всю жизнь» об источнике — только если это есть в данных.
- distinction — общая мысль о вещах, без утверждения, что она верна про ЭТОГО человека («признать предел не значит сдаться», «узнать ещё не значит понять»).
- question — догадку, которую нельзя подтвердить словами человека, можно оставить только как вопрос («Что в его отказе вы считаете его решением?»). Не превращай каждое сомнение в вопрос: вопрос к себе остаётся живым и содержательным, а не анкетой.
- impersonal_example — пример без «вы» и без третьих лиц, который никому не приписывает новое действие, качество или обстоятельство («должность — то, что можно потерять вместе с работой»).
- open_hypothesis — содержательная гипотеза, которую подсказывает источник, о том, чего человек не говорил: причина его чувства, мотив, намерение, выбор, скрытое представление, что думают или чувствуют другие, где проходит граница между «ролью» и «мной». Её можно предложить ТОЛЬКО открыто, чтобы человек сам проверил, относится ли она к нему: вопросом или словами вроде «возможно», «может быть», «здесь можно проверить», «Эпиктет предлагает различить…». Для open_hypothesis evidence — ДОСЛОВНО то предложение поля, где она сказана (код проверит, что оно открытое). В title гипотеза о человеке недопустима: заголовок называет различение о вещах («Событие и чужой взгляд на него — разные вещи»), а не объясняет его чувство («Стыдно бывает не за событие, а за чужую жалость» — нельзя). На вопрос «кто я теперь» не решай за человека, что было «ролью», а что «им самим» («место уходит, а человек остаётся» — нельзя): предложи это различение для его собственной проверки. Пиши естественно, без канцелярских оговорок в каждой фразе: открытая форма нужна там, где гипотеза, а не везде.
Всё остальное — НОВЫЙ ДОМЫСЕЛ. Его нельзя писать как факт: убери, переведи в вопрос или скажи как общую мысль (distinction). Особенно:
- не приписывай ни человеку, ни другим людям мотивы, причины, мысли, чувства, желания, намерения, отношение к себе, способности, привычки, «свободный выбор» или неспособность выбирать; не решай, что именно ограничивает болезнь и что человек «выбирает сам»;
- не придумывай бытовых сцен ради конкретности (ужин, прогулка, разговор перед сном, новое дело), если человек о них не писал; пример бери из его же слов («Вы сами пишете, что по утрам не знаете, куда себя деть») или делай обезличенным;
- не предлагай от себя вариантов поведения («можно пока ничего не говорить сыну», «выйти пройтись») — особенно о детях, здоровье, отношениях и решениях, которые касаются других людей. Оставайся на уровне различения («запретить и ничего не делать — не единственные способы понимать действие») и спроси.
- если человек назвал тревогу — не пиши «боитесь»; если «стыдно» — исследуй стыд, но не объясняй, почему ему стыдно.
«Подробнее» должно добавить хотя бы один НОВЫЙ смысловой элемент по сравнению с main_idea и applied_insight: промежуточный шаг рассуждения источника, внутреннюю структуру аргумента, различение внутри источника, связь двух частей данных карточки или объяснение, почему из источника возникает именно эта перспектива. Пересказ того же другими словами — не новый элемент. Назови его во внутреннем поле detail_new_element (kind и одна фраза). Если в данных карточки нового элемента нет — kind = none, и тогда «Подробнее» не длиннее 40 слов.
Запиши этот разбор во внутреннее поле grounding (человек его не видит): по одной записи на каждое утверждение о человеке, о другом человеке или об источнике, включая примеры. evidence для user_fact — ДОСЛОВНЫЙ отрывок из слов человека, для source_fact — ДОСЛОВНЫЙ отрывок из данных карточки (скопируй точно, 2–12 слов); для остальных видов evidence может быть пустым. Отрывки проверяются кодом: если такого отрывка в данных нет — ответ отклонят. Утверждение, которое ты не можешь так подтвердить, не пиши как факт; если в разборе остался new_inference — ответ отклонят, сначала убери или переформулируй это место.

Отвечай по-русски, строго по JSON-схеме."""

# ------------------------------------------------------------------ MVP pass 1: the final-corpus card
# quote (shown by code, on top) → comment: what distinction the author makes → application to the question → ONE question.
FINAL_FORMAT = "final-mvp"
FINAL_WRITER_PROMPT_VERSION = "final-card-writer-prompt/1.0.0"
FINAL_FIELDS = ("main_idea", "applied_insight", "reflection_question")
FINAL_EXCERPT_FROM_WORDS = 40  # a longer verified quote is shown as a VERBATIM excerpt; the whole quote stays one tap away
FINAL_ADVICE = (r"\bсделайте\b", r"\bпопробуйте\b", r"\bпостарайтесь\b", r"\bпозвольте себе\b", r"\bвам стоит\b")

FINAL_WRITER_PROMPT = f"""Ты пишешь ОДНУ карточку философского навигатора для обычного человека. Карточку уже выбрали: известно, какой источник и какое различение она даёт. Человек увидит карточку так:
1) НАВЕРХУ — дословная цитата источника и подпись «автор · произведение · место» (это делает код, не ты);
2) комментарий к цитате (поле main_idea);
3) применение к вопросу человека (поле applied_insight);
4) один вопрос на подумать (поле reflection_question).
Больше в карточке ничего нет: ни заголовка, ни пояснений, ни «Подробнее». Каждая мысль звучит ОДИН раз.

main_idea — КОММЕНТАРИЙ К ЦИТАТЕ: какое различение здесь делает автор — что он отделяет от чего. 1–2 коротких предложения, всего не больше 35 слов. Можно назвать автора или книгу («Эпиктет различает…», «В Екклесиасте…»). НЕ пересказывай цитату её же словами и не копируй её архаичный синтаксис: человек только что её прочитал. Здесь ещё нет человека.
applied_insight — ПРИМЕНЕНИЕ: почему это различение важно именно в ситуации человека. 1–3 коротких предложения, всего не больше 45 слов. Опирайся на его слова («Вы пишете…», «Вы спрашиваете…»). Не советуй и не предписывай: никаких «вам следует», «вам нужно», «сделайте», «попробуйте».
reflection_question — РОВНО ОДИН короткий понятный вопрос к себе от первого лица, не больше 18 слов, ровно один знак «?». Не два вопроса подряд («Что я думаю о её ответе? И чего хочу после него?» — нельзя; нужно: «Чего я на самом деле хочу после её ответа?»). Конкретный, о его ситуации; не философская загадка и не совет.
quote_excerpt — заполняй, ТОЛЬКО если в данных «проверенная_дословная_цитата» длиннее 40 слов: скопируй из неё ДОСЛОВНО (символ в символ, без пропусков внутри) один непрерывный отрывок 12–40 слов, который точнее всего несёт различение карточки. Ничего не меняй в словах. Если цитата короткая — пустая строка.

ЯЗЫК — главное требование:
- Современный естественный русский, понятный с первого чтения. Пиши так, как умный друг сказал бы вслух.
- Упрощай язык, а не мысль: различение должно остаться точным.
- Конкретные слова: кто что делает, видит, говорит, хочет. Минимум отвлечённых существительных («устройство», «участие», «измерение», «отношение к»), никакого канцелярита и псевдофилософского пафоса.
- Не превращай мысль в загадочный афоризм. Плохо: «Указание ещё не показывает другому, как ты видишь дело». Хорошо: «Другой человек может видеть ситуацию иначе». Плохо: «Известие о чужом чувстве — не известие о моём выборе». Хорошо: «Её чувство говорит о ней. Оно не решает за вас, как поступить».
- Короткие предложения: не длиннее 18 слов.
- Названия произведений в связном тексте — в кавычках-ёлочках: «Беседы» Эпиктета, «Дао дэ цзин». Священные книги (Библия, Евангелие, Коран, Тора) без кавычек.

{LANGUAGE_RULES}

ПРАВДА О ЧЕЛОВЕКЕ И ОБ ИСТОЧНИКЕ:
- О человеке — только то, что он сам сказал или выбрал (его слова и выбранные чувства даны). Не добавляй мотивов, причин, неназванных чувств, диагнозов («ревность», если он так не сказал), специалистов, сцен и сроков. {AMPLIFICATION_RULE} {PSYCH_FUNCTION_RULE} {INTERNAL_CLAIM_RULE}
- Догадку о человеке можно предложить только открыто, для его проверки (вопросом или «возможно»).
- Об источнике — только то, что есть в данных карточки (цитата, ход текста). Никаких подробностей из памяти. Не называй номера глав, стихов, параграфов: ссылка показывается отдельно.
- Не пиши, что автор «предложил бы» или «сказал бы вам». Источник даёт мысль, применяет её система.
- Не предписывай, как чувствовать. «Кто я» за человека не решай.
- Сохраняй опорные слова человека: «принять» ≠ «смириться». Если «род_человека» = «неизвестен», пиши без форм, зависящих от рода.
- Чувства, которые человек выбрал, — подсказка, ЧТО в вопросе для него живо. Не вставляй их названия ради галочки.

Запиши во внутреннее поле grounding (человек его не видит) по записи на каждое утверждение о человеке, о другом человеке или об источнике: kind = user_fact (evidence — ДОСЛОВНЫЙ отрывок 2–12 слов из слов человека), source_fact (ДОСЛОВНЫЙ отрывок из данных карточки), distinction, question, impersonal_example или open_hypothesis (evidence — дословно то предложение поля, где она сказана). Отрывки проверяет код. metaphor_words — слова-образы источника (их нельзя переносить на ситуацию человека).

Отвечай по-русски, строго по JSON-схеме."""

FINAL_WRITER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [*FINAL_FIELDS, "quote_excerpt", "grounding", "metaphor_words"],
    "properties": {
        **{f: {"type": "string"} for f in FINAL_FIELDS},
        "quote_excerpt": {"type": "string"},
        "grounding": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["field", "claim", "kind", "evidence"],
                "properties": {
                    "field": {"type": "string", "enum": list(FINAL_FIELDS)},
                    "claim": {"type": "string"},
                    "kind": {"type": "string", "enum": ["user_fact", "source_fact", "distinction", "question",
                                                        "impersonal_example", "open_hypothesis", "new_inference"]},
                    "evidence": {"type": "string"},
                },
            },
        },
        "metaphor_words": {"type": "array", "items": {"type": "string"}},
    },
}

GROUNDING_KINDS = ("user_fact", "source_fact", "distinction", "question", "impersonal_example")
DETAIL_KINDS = ("reasoning_step", "argument_structure", "inner_distinction", "link_between_parts", "why_this_perspective",
                "none")
SHORT_DETAIL_WORDS = 40  # «Подробнее» without a new element must be short
WRITER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [*USER_FIELDS, "grounding", "metaphor_words", "detail_new_element"],
    "properties": {
        **{f: {"type": "string"} for f in USER_FIELDS},
        # M3.3.2 internal provenance audit (never shown): every claim about the person, a third person or the source
        "grounding": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["field", "claim", "kind", "evidence"],
                "properties": {
                    "field": {"type": "string", "enum": list(USER_FIELDS)},
                    "claim": {"type": "string"},
                    "kind": {"type": "string", "enum": [*GROUNDING_KINDS, "open_hypothesis", "new_inference"]},
                    "evidence": {"type": "string"},
                },
            },
        },
        # M3.4.1: the source's surface images (not to be carried onto the person's situation)
        "metaphor_words": {"type": "array", "items": {"type": "string"}},
        # M3.4.1: what «Подробнее» adds beyond the main card (semantic novelty, self-reported, length-checked)
        "detail_new_element": {
            "type": "object", "additionalProperties": False, "required": ["kind", "what"],
            "properties": {"kind": {"type": "string", "enum": list(DETAIL_KINDS)}, "what": {"type": "string"}},
        },
    },
}


class WriterUnavailable(RuntimeError):
    pass


@dataclass
class ClaudeCodeCLIWriter:
    model: str = "claude-opus-5-5"
    timeout_s: int = 300
    name: str = "claude-code-cli"
    effort: str | None = None  # `claude --effort` (low / medium / high …); None = CLI default

    def complete(self, brief: dict, feedback: str | None = None) -> tuple[dict, dict]:
        user = "Карточка (JSON):\n" + json.dumps(brief, ensure_ascii=False, indent=1)
        if feedback:
            user += "\n\nПредыдущий вариант не прошёл проверку. Исправь только это, остальное сохрани. Причина:\n" + feedback
        final = brief.get("формат_карточки") == FINAL_FORMAT
        cmd = [
            "claude", "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
            "--model", self.model, "--system-prompt", FINAL_WRITER_PROMPT if final else WRITER_PROMPT,
            "--output-format", "json",
            "--json-schema", json.dumps(FINAL_WRITER_SCHEMA if final else WRITER_SCHEMA, ensure_ascii=False),
            *(["--effort", self.effort] if self.effort else []),
        ]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=self.timeout_s)
            payload = json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise WriterUnavailable(str(exc)[:500]) from exc
        if payload.get("is_error") or not isinstance(payload.get("structured_output"), dict):
            raise WriterUnavailable(cli_error_message(payload))
        return payload["structured_output"], cli_usage(payload, time.monotonic() - t0)


def user_words_from_package(package: dict) -> str:
    ctx = package.get("context") or {}
    return " ".join([package.get("confirmed_question", ""), ctx.get("circumstance") or "", ctx.get("narrative") or "",
                     *package.get("experiences", [])])


def build_brief(package: dict, selected: dict, others: list[dict], fragment: Fragment) -> dict:
    cand = next(c for c in package["candidates"] if c["card_id"] == selected["card_id"])
    t = fragment.technical
    ctx = package.get("context") or {}
    final = fragment.technical.corpus_status == "final_2026_10_07" and bool(fragment.fragment)
    return {
        **({"формат_карточки": FINAL_FORMAT} if final else {}),
        "слова_человека": {
            "подтверждённый_вопрос": package["confirmed_question"],
            "рассказ": ctx.get("narrative"),
            "обстоятельства": ctx.get("circumstance"),
            "переживания": package.get("experiences", []),
        },
        "источник": {
            "ссылка_показывается_отдельно": display_label(fragment) if final else fragment_reference(fragment),
            "описание_в_корпусе_учёным_языком_не_переносить_слова": cand["perspective"],
            "ход_текста": getattr(t, "launch_philosophical_move", None),
            **({"проверенная_дословная_цитата": fragment.fragment}
               if fragment.technical.corpus_status == "final_2026_10_07" and fragment.fragment else {}),
        },
        "различение_карточки": selected["distinction"],
        "эффект_перспективы": selected.get("perspective_effect"),
        "род_человека": {"f": "женский", "m": "мужской"}.get(person_gender(user_words_from_package(package)), "неизвестен"),
        "пересказ_отбора_не_основание": selected.get("source_point"),
        "что_это_значит_для_вопроса": selected.get("user_point"),
        "различения_других_карточек_не_повторять": [o["distinction"] for o in others],
    }


def _norm(text: str) -> str:
    return " ".join(re.findall(r"\w+", (text or "").lower().replace("ё", "е")))


_SECOND_PERSON = r"\b(?:вы|вас|вам|вами|ваш\w*)\b"


def grounding_problems(audit, user_words: str, source_data: str, fields: dict | None = None) -> list[str]:
    """M3.3.2: provenance of every claim the writer made about the person, a third person or the source.
    user_fact / source_fact must quote the person's words / the corpus card data verbatim (checked here);
    an inference the writer itself marks as new is rejected. Semantic completeness is judged by the control runs."""
    if not isinstance(audit, list):
        return ["grounding audit is missing: list every claim about the person, another person or the source"]
    uw, sd = _norm(user_words), _norm(source_data)
    out = []
    kinds = {e.get("kind") for e in audit}
    if "source_fact" not in kinds:
        out.append("grounding audit has no source_fact: show which card data the source explanation rests on")
    if "user_fact" not in kinds:
        out.append("grounding audit has no user_fact: show which of the person's own words the application rests on")
    for e in audit:
        kind, claim, ev = e.get("kind"), (e.get("claim") or "").strip(), _norm(e.get("evidence"))
        # The claim is the writer's own short retelling, so only the verbatim evidence is compared with the data.
        if kind == "new_inference":
            out.append(f"new inference stated as a fact ({e.get('field')}): «{claim[:160]}» — remove it, "
                       "ask it as a question or say it as a general distinction")
        elif kind == "user_fact" and (not ev or ev not in uw):
            out.append(f"not in the person's own words ({e.get('field')}): «{claim[:160]}»; evidence "
                       f"«{e.get('evidence', '')[:120]}» is not found — keep only what they said")
        elif kind == "source_fact" and (not ev or ev not in sd):
            out.append(f"not in the card data ({e.get('field')}): «{claim[:160]}»; evidence "
                       f"«{e.get('evidence', '')[:120]}» is not found — do not add knowledge about the source")
        elif kind == "open_hypothesis":
            field = e.get("field")
            sent = (e.get("evidence") or "").strip()
            if field == "title":
                out.append(f"a hypothesis about the person in the title: «{claim[:160]}» — the title names a distinction "
                           "about things, it does not explain the person's feeling or motive")
            elif fields is not None and (not sent or _norm(sent) not in _norm(fields.get(field, ""))):
                out.append(f"open_hypothesis evidence must be the exact sentence of {field} where it is said: "
                           f"«{sent[:120]}» is not found")
            elif not is_open_formulation(sent):
                out.append(f"a hypothesis about the person is stated as a fact ({field}): «{sent[:160]}» — offer it "
                           "for them to check (a question, «возможно», «можно проверить», «… предлагает различить»)")
        elif kind == "impersonal_example" and re.search(_SECOND_PERSON, claim, flags=re.IGNORECASE):
            out.append(f"an example about the person is not impersonal ({e.get('field')}): «{claim[:160]}» — take "
                       "the example from their own words or make it impersonal")
    return out


def _ngrams(text: str, n: int) -> set:
    w = _norm(text).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def verbatim_excerpt(quote: str, excerpt: str) -> str | None:
    """The writer's excerpt if it is a real verbatim piece of the quote (whitespace-insensitive), else None."""
    ex = re.sub(r"\s+", " ", (excerpt or "").strip())
    q = re.sub(r"\s+", " ", quote or "")
    if not ex or ex == q or not (8 <= word_count(ex) <= 45):
        return None
    return ex if ex in q else None


def lead_excerpt(quote: str, max_words: int = FINAL_EXCERPT_FROM_WORDS) -> str:
    """Fallback: the leading whole sentences of the quote, verbatim, up to ``max_words`` (at least the first one)."""
    q = re.sub(r"\s+", " ", quote).strip()
    parts = re.split(r"(?<=[.!?…;])\s+", q)
    out = parts[0]
    for part in parts[1:]:
        if word_count(out + " " + part) > max_words:
            break
        out += " " + part
    return out


def check_final_card(card_id: str, fields: dict, selected: dict, source: str, user_words: str,
                     source_data: str | None, quote: str | None) -> Perspective:
    """MVP pass 1: the final-corpus card (comment, application, exactly one question; the quote is shown by code)."""
    missing = [f for f in FINAL_FIELDS if not isinstance(fields.get(f), str) or not fields[f].strip()]
    if missing:
        raise ValueError(f"empty fields: {missing}")
    f = {k: quote_work_titles(fields[k].strip()) for k in FINAL_FIELDS}
    everything = " ".join(f.values())
    hits = amplification_hits(everything)
    if hits:
        raise ValueError(f"states an unconfirmed hypothesis about the person as fact: {hits}")
    advice = [p for p in FINAL_ADVICE if re.search(p, everything, flags=re.IGNORECASE)]
    if advice:
        raise ValueError(f"advice to the person ({advice}); describe the distinction, do not tell them what to do")
    unnamed = unnamed_person_claims(f["applied_insight"] + " " + f["reflection_question"], user_words)
    if unnamed:
        raise ValueError(f"brings in what the person did not name ({unnamed}); speak only from their own words")
    if false_precision_hits(f["main_idea"] + " " + f["applied_insight"]):
        raise ValueError("chapter/verse numbers or §-references inside the text; the reference is shown separately")
    shifted = anchor_shift_hits(f["applied_insight"] + " " + f["reflection_question"], user_words)
    if shifted:
        raise ValueError(f"the person's own word was replaced by a near-synonym that changes the frame: {shifted}")
    if quote and _ngrams(f["main_idea"], 6) & _ngrams(quote, 6):
        raise ValueError("the comment retells the quote in its own words; the person has just read the quote — say "
                         "what distinction the author makes, in plain modern words")
    if person_gender(user_words) is None:
        gendered = gendered_first_person_hits(f["applied_insight"] + " " + f["reflection_question"])
        if gendered:
            raise ValueError(f"the person's gender is unknown, but the text uses gendered forms: {gendered[:3]}")
    horizons = invented_horizon_hits(everything, user_words)
    if horizons:
        raise ValueError(f"invented time horizon the person never named: {horizons[:3]}")
    simulated = author_simulation_hits(everything)
    if simulated:
        raise ValueError(f"the source's author is made to speak to the person ({simulated[:2]})")
    carried = stem_hits(fields.get("metaphor_words") or [], f["applied_insight"] + " " + f["reflection_question"])
    if carried:
        raise ValueError(f"the source's image is carried onto the person's situation: {carried}; keep the distinction")
    if source_data is not None:
        problems = grounding_problems(fields.get("grounding"), user_words, source_data, f)
        if problems:
            raise ValueError("grounding: " + " | ".join(problems[:4]))
    excerpt = None
    if quote and word_count(quote) > FINAL_EXCERPT_FROM_WORDS:
        excerpt = verbatim_excerpt(quote, fields.get("quote_excerpt") or "") or lead_excerpt(quote)
    try:
        return Perspective(card_id=card_id, role=selected["role"].strip(), source=source,
                           why_selected=selected["why_selected"].strip(), distinction=selected["distinction"].strip(),
                           main_idea=f["main_idea"], applied_insight=f["applied_insight"],
                           reflection_question=f["reflection_question"], card_format=FINAL_FORMAT,
                           quote_excerpt=excerpt)
    except ValidationError as exc:
        raise ValueError(str(exc)[:1200]) from exc


def check_card(card_id: str, fields: dict, selected: dict, source: str, user_words: str,
               source_data: str | None = None, final_quote: str | None = None) -> Perspective:
    """Contract + language checks for one written card. Raises ValueError with a reason for the writer.
    ``final_quote`` set → the final-corpus MVP card (``check_final_card``)."""
    if final_quote is not None:
        return check_final_card(card_id, fields, selected, source, user_words, source_data, final_quote)
    missing = [f for f in USER_FIELDS if not isinstance(fields.get(f), str) or not fields[f].strip()]
    if missing:
        raise ValueError(f"empty fields: {missing}")
    f = {k: quote_work_titles(fields[k].strip()) for k in USER_FIELDS}  # M3.4: «Бхагавад-гита» in prose, by code
    everything = " ".join(f.values())
    hits = amplification_hits(everything)
    if hits:
        raise ValueError(f"states an unconfirmed hypothesis about the person as fact: {hits}")
    unnamed = unnamed_person_claims(" ".join(f[k] for k in PERSON_FIELDS), user_words)
    if unnamed:
        raise ValueError(f"brings in what the person did not name ({unnamed}); speak only from their own words")
    precise = false_precision_hits(" ".join([f["main_idea"], f["applied_insight"], f["perspective"],
                                             f["question_explanation"]]))
    if precise:
        raise ValueError("chapter/verse numbers or §-references inside the text sound like a checked quote; "
                         "retell the idea without numbers (the reference is shown separately)")
    meta = meta_hits(f["perspective"])  # the main card is checked by the contract; «Подробнее» here
    if meta:
        raise ValueError(f"philosophical meta-language in «Подробнее»: {meta}")
    shifted = anchor_shift_hits(" ".join(f[k] for k in (*PERSON_FIELDS, "perspective")), user_words)
    if shifted:
        raise ValueError(f"the person's own word was replaced by a near-synonym that changes the frame: {shifted} "
                         "(«принять» is not «смириться»); keep their word")
    retold = retold_sentences(f["perspective"], " ".join([f["main_idea"], f["applied_insight"],
                                                          f["question_explanation"]]))
    if len(retold) >= 2:  # M3.4: «Подробнее» deepens the source's reasoning, it does not retell the card
        raise ValueError("«Подробнее» repeats the card instead of going deeper: " + " | ".join(r[:100] for r in retold[:3])
                         + " — show how the source's reasoning leads to the distinction, or make it shorter")
    if ambiguous_second_question(f["reflection_question"]):
        raise ValueError("the second question points back with a bare pronoun («в нём», «его»…); name the thing again")
    if person_gender(user_words) is None:  # M3.4.1: gender unknown → no gendered first-person forms
        gendered = gendered_first_person_hits(" ".join(f[k] for k in (*PERSON_FIELDS, "perspective")))
        if gendered:
            raise ValueError(f"the person's gender is unknown, but the text uses gendered forms: {gendered[:3]}; "
                             "rephrase neutrally (not «готов(а)»)")
    horizons = invented_horizon_hits(" ".join(f[k] for k in USER_FIELDS), user_words)
    if horizons:
        raise ValueError(f"invented time horizon the person never named: {horizons[:3]}; ask openly about the consequences")
    simulated = author_simulation_hits(" ".join(f[k] for k in USER_FIELDS))
    if simulated:
        raise ValueError(f"the source's author is made to speak to the person ({simulated[:2]}); the source gives the "
                         "idea, the application is ours: «Это различение позволяет спросить…»")
    carried = stem_hits(fields.get("metaphor_words") or [], " ".join(f[k] for k in PERSON_FIELDS))
    if carried:
        raise ValueError(f"the source's image is carried onto the person's situation: {carried}; keep the distinction, "
                         "not the metaphor's words, in the application, the question and «Что имеется в виду?»")
    dne = fields.get("detail_new_element")
    if isinstance(dne, dict) and dne.get("kind") == "none" and word_count(f["perspective"]) > SHORT_DETAIL_WORDS:
        raise ValueError(f"«Подробнее» adds nothing new ({word_count(f['perspective'])} words): add a step or structure "
                         f"of the source's reasoning from the card data, or make it at most {SHORT_DETAIL_WORDS} words")
    if source_data is not None:  # M3.3.2 provenance audit (the live writer always returns it)
        problems = grounding_problems(fields.get("grounding"), user_words, source_data, f)
        if problems:
            raise ValueError("grounding: " + " | ".join(problems[:4]))
    try:
        return Perspective(card_id=card_id, role=selected["role"].strip(), source=source,
                           why_selected=selected["why_selected"].strip(), distinction=selected["distinction"].strip(),
                           title=f["title"], main_idea=f["main_idea"], applied_insight=f["applied_insight"],
                           reflection_question=f["reflection_question"], question_explanation=f["question_explanation"],
                           perspective=f["perspective"])
    except ValidationError as exc:
        raise ValueError(str(exc)[:1200]) from exc


def source_data_from_brief(brief: dict) -> str:
    """The only ground for claims about the source: corpus card data (never the selector's own retelling)."""
    src = brief["источник"]
    return " ".join(str(v) for v in (src.get("ссылка_показывается_отдельно"),
                                     src.get("описание_в_корпусе_учёным_языком_не_переносить_слова"),
                                     src.get("ход_текста"), src.get("проверенная_дословная_цитата")) if v)


def write_card(brief: dict, selected: dict, source: str, user_words: str, writer, max_attempts: int = 3,
               validator=None) -> tuple[Perspective | None, dict]:
    record = {"card_id": selected["card_id"], "attempts": 0, "repairs": [], "calls": [], "fallback": False,
              "validation": []}
    source_data = source_data_from_brief(brief)
    feedback = None
    t0 = time.monotonic()
    for attempt in range(1, max_attempts + 1):
        record["attempts"] = attempt
        t_call = time.monotonic()
        fields, usage = writer.complete(brief, feedback)
        record["calls"].append({**usage, "attempt": attempt, "call_seconds": round(time.monotonic() - t_call, 2)})
        try:
            final_quote = brief["источник"].get("проверенная_дословная_цитата") \
                if brief.get("формат_карточки") == FINAL_FORMAT else None
            card = check_card(selected["card_id"], fields, selected, source, user_words, source_data, final_quote)
            if validator is not None:  # M3.4.2: independent of the writer's own audit
                validate_independently(card, brief, validator, record)
            record["grounding"] = fields.get("grounding")
            record["seconds"] = round(time.monotonic() - t0, 2)
            return card, record
        except ValueError as exc:
            feedback = str(exc)[:1200]
            record["repairs"].append(feedback)
    record["seconds"] = round(time.monotonic() - t0, 2)
    record["fallback"] = True  # could not be written cleanly: the card is dropped (never shown half-checked)
    return None, record


def validate_independently(card: Perspective, brief: dict, validator, record: dict) -> None:
    """Run the independent grounding validator on the final text; raise ValueError (→ targeted rewrite) on a violation.
    The validator gets the person's words, the source material and the card text — never the writer's audit."""
    from navigator.composition.grounding_validator import feedback_for, validation_material, violations_of

    text = {k: getattr(card, k) for k in ("title", "main_idea", "applied_insight", "reflection_question",
                                          "question_explanation", "perspective") if getattr(card, k)}
    src = brief["источник"]
    material = validation_material(
        {k: v for k, v in brief["слова_человека"].items() if v},
        {"ссылка": src.get("ссылка_показывается_отдельно"),
         "описание_в_корпусе": src.get("описание_в_корпусе_учёным_языком_не_переносить_слова"),
         "ход_текста": src.get("ход_текста"),
         **({"проверенная_дословная_цитата": src["проверенная_дословная_цитата"]}
            if src.get("проверенная_дословная_цитата") else {})},
        text)
    t_call = time.monotonic()
    out, usage = validator.complete(material)
    bad = violations_of(out, text)
    record["validation"].append({**usage, "call_seconds": round(time.monotonic() - t_call, 2),
                                 "checked": len(out.get("sentences") or []), "violations": bad,
                                 "labels": [(x.get("field"), x.get("label")) for x in out.get("sentences") or []]})
    if bad:
        raise ValueError(feedback_for(bad))


def write_cards(package: dict, selection: list[dict], fragments: list[Fragment], source_of, writer,
                max_attempts: int = 3, validator=None) -> tuple[list[Perspective | None], list[dict]]:
    """Write all selected cards in parallel (one call per card). Order of ``selection`` is kept."""
    by_id = {f.id: f for f in fragments}
    words = user_words_from_package(package)

    def one(i: int):
        sel = selection[i]
        brief = build_brief(package, sel, [s for j, s in enumerate(selection) if j != i], by_id[sel["card_id"]])
        return write_card(brief, sel, source_of(sel["card_id"]), words, writer, max_attempts, validator)

    with ThreadPoolExecutor(max_workers=max(1, len(selection))) as ex:
        results = list(ex.map(one, range(len(selection))))
    return [r[0] for r in results], [r[1] for r in results]

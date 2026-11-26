# STRATA_STAGE_TRIM

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

GPU の layer split で、各 GPU の重み arena から自分が実行しない層の dense weights を除き、その分の VRAM を expert cache などに残すかを制御する。CUDA/HIP 実装では通常の layer split で trim が既定で有効であり、SYCL 実装では環境変数か --trim-stage-weights が必要。PLE tensors は各 GPU に残る。環境変数だけで layer split を開始することはなく、layer split 自体が有効な場合に限って作用する（engine/src/program/generate.cpp:5827-5841,5951-5957,5978-5982,6924-6957、engine/sycl/src/program/generate.cpp:3086-3108,3126-3130）。

## 値と判定

CUDA/HIP は getenv の値全体を文字列比較し、空でないかも調べる。unset と空文字は環境変数からの明示的な ON/OFF として扱わない。空白除去・数値変換・大文字小文字変換はない。SYCL も同様に、unset・空文字・文字列全体が "0" の場合を false、それ以外の非空文字列を true とする。ただし SYCL は "0" を CLI の trim 要求に対する OFF override には使わない（engine/src/program/generate.cpp:5836-5841、engine/sycl/src/program/generate.cpp:3092-3095）。

| 実装・条件 | unset / 空文字 | 設定値で trim 要求が有効 | 設定値で無効 |
|---|---|---|---|
| CUDA/HIP、layer split | 環境変数自身は要求しないが、通常の split trim は既定 ON | 空でない文字列で、全体が "0" でない値（例: 1, true, false, 空白+0, 0anything） | 全体がちょうど "0" |
| SYCL、layer split | 環境変数自身は要求しない。エンジン既定は OFF | 空でない文字列で、全体が "0" でない値（例: 1, true, false, 空白+0, 0anything） | unset、空文字、または全体がちょうど "0" |

CUDA/HIP では --trim-stage-weights が STRATA_STAGE_TRIM=0 より優先し、--no-trim-stage-weights は非ゼロの環境値より優先する。両方の CLI flag が並ぶ場合は parser が後に読んだ方が trim_stage_flag を設定する。SYCL には --no-trim-stage-weights がなく、--trim-stage-weights は環境値 "0" より優先する。Intel の setup_intel.py は split 設定の env に setdefault("STRATA_STAGE_TRIM", "1") を行うため、ユーザーが既に設定した値はそのまま残る（engine/src/program/generate.cpp:4043,4120,5839-5841、engine/sycl/src/program/generate.cpp:668,2039,3092-3095、engine/sycl/setup_intel.py:541-550）。

CUDA/HIP の低 VRAM spill walk は通常の trim flag と別に trim を決定する経路がある。従って --no-trim-stage-weights だけでは、カードが短く STRATA_SPILL_OFF が unset の discrete GPU で、その自動 trim を止めない場合がある。STRATA_STAGE_TRIM=0 は両 spill walk の guard にも使われ、自動 trim を抑止する。STRATA_SPLIT_EARLY_OFF は auto split の早期 spill walk のみを止める（engine/src/program/generate.cpp:5854-5856,6074-6096）。

## 有効になる条件

- CUDA/HIP 実装は CUDA/HIP engine、SYCL 実装は SYCL engine でそれぞれ判定する。ソース上の別実装間に共通の設定状態はない（engine/src/program/generate.cpp:5836-5841、engine/sycl/src/program/generate.cpp:3092-3102）。
- layer split は server mode の --serve と --layer-split K[,K2...] または --layer-split auto を必要とし、CUDA/HIP 側は指定 split 点に対応する GPU を必要とする。変数だけを設定しても split は作られない（engine/src/program/generate.cpp:4774-4809,4848-4850）。
- CUDA/HIP の通常 trim は multi_gpu && !split_auto && !split_at.empty() のとき有効になる。--layer-split auto では split 点決定後の stage weights を遅延ロードする。CUDA0 の早期 trim は split が既知の場合に限られ、後続 GPU の trim は split 決定後に行われる（engine/src/program/generate.cpp:5951-5957,5978-5982,6677-6682）。
- CUDA/HIP の自動 spill trim は spill_discrete_gpu() が true で、後続カードが split_walk::trim_needed に該当したときだけ行う。早期 auto 経路では加えて STRATA_SPILL_OFF と STRATA_SPLIT_EARLY_OFF が unset で、STRATA_STAGE_TRIM が正確な "0" でないことが条件。後段 walk は STRATA_SPILL_OFF と正確な "0" を確認する（engine/src/program/generate.cpp:5854-5856,6074-6096）。
- SYCL の通常 trim は環境変数または --trim-stage-weights が真で、multi-GPU split の場合に有効。auto では late_weights により split search 後に各 stage の重みをロードする（engine/sycl/src/program/generate.cpp:3092-3108,3703-3708,3885-3891,4210-4218）。
- setup_intel.py が変数を 1 に補うのは Intel setup 内で split と判定された構成に限る。既存の config env 値は setdefault で保持する（engine/sycl/setup_intel.py:541-550）。

## 実行時の詳細

CUDA/HIP ではモデル重みのロード前に環境値を読み、trim_off、trim_user_asked、trim_asked を作る。auto split の早期 walk は重みサイズを pack index から見積もって空き容量を調べ、必要なら split 点を決めて全カードを trim する。早期 walk が使われない場合、CUDA0 の重みロード後に後続カードの空き容量と必要量を調べる spill walk があり、短いカードに限り後続 stage を trim する。通常の明示 split は各カードの blk.<layer> を自身の範囲外で skip し、PLE tensors は skip 対象から除外する。後続 stage の重み arena が収まらなければ layer split, CUDA%d weights: ... を stderr に出して起動を失敗させる（engine/src/program/generate.cpp:5836-5841,5854-5942,5978-5982,6074-6102,6640-6656,6932-6957）。

SYCL は env 判定を startup 時に lambda で一度評価し、要求状態を trim_asked に保持する。通常 split では各 stage の範囲外の dense tensors を除いた arena をロードし、auto では split search が終わった後に範囲を確定してロードする。実行中またはリクエストごとの再評価はこのコードにない（engine/sycl/src/program/generate.cpp:3092-3108,3650-3664,3703-3708,4210-4218）。CUDA/HIP の環境値は初期判定のほか spill walk の guard で同じ起動処理中に再度 getenv されるが、static cache はしていない（engine/src/program/generate.cpp:5836-5838,5855,6075）。

trim が実行されると各 GPU は自身の担当層の dense weights を保持し、他層分として使っていた VRAM が expert cache 等に回る。ソースコメントは trim 自体を bit-exact と記すが、trim によって増減する expert cache の保持数は変わり得る。出力 token や選択結果が常に同一とはこの環境変数のコードからは保証できない（engine/src/program/generate.cpp:6924-6957、docs/MULTI_GPU.md:170,223-224）。

## ログと測定値

- trim を明示したのに multi-GPU split がない場合、CUDA/HIP と SYCL は stderr に strata generate: --trim-stage-weights needs a layer split across GPUs (ignored) を出す。環境変数だけで ON になった場合はこの flag 条件に入らない（engine/src/program/generate.cpp:5951-5953、engine/sycl/src/program/generate.cpp:3102-3104）。
- CUDA0 が通常 trim されると strata generate: layer split: CUDA0 loads the dense weights of layers ... only を出す。auto split の早期 walk は空き容量・必要量・選択 split を含む strata generate: short of GPU memory: ... を出す。後段 spill walk は短い GPU と必要容量を示す同系統のログを出す（engine/src/program/generate.cpp:5980-5982,5932-5936,6090-6094）。
- SYCL の CUDA0 trim も同じ CUDA0 loads the dense weights... 形式のログを出す。後続 stage の load_stage_weights は失敗時に strata generate: layer split, CUDA%d weights: ... を出し、呼び出し元は終了値 1 で終了する（engine/sycl/src/program/generate.cpp:3126-3130,3650-3679,3705-3708）。
- docs/MULTI_GPU.md は STRATA_STAGE_TRIM=0 がコピーを保持すると説明する。現行 CUDA/HIP コードでも exact "0" は通常 trim と spill walk の両方を止める。一方 --no-trim-stage-weights は spill walk の guard に含まれないため、短い discrete GPU で自動 trim が起き得る点は文書の単純な同等表現より条件が細かい（docs/MULTI_GPU.md:166-170,223-224、engine/src/program/generate.cpp:5839-5841,6074-6096）。

## 根拠

- engine/src/program/generate.cpp:5836-5841 — env 値の判定、CLI との優先順位。
- engine/src/program/generate.cpp:5854-5957,6074-6102 — auto / spill walk 条件と stage trim 判定。
- engine/src/program/generate.cpp:5978-5982,6640-6656,6677-6682,6924-6957 — skip 対象、重みロード、失敗ログ、cache 容量計算。
- engine/sycl/src/program/generate.cpp:3092-3108,3126-3130,3650-3679,3703-3708,3885-3891,4210-4218 — SYCL の値判定・適用・ロード時期・失敗経路。
- engine/sycl/setup_intel.py:541-550 — split 構成への既定 env 値設定。
- docs/MULTI_GPU.md:166-170,215-224、docs/BATCHING.md:98 — 資料との照合。性能測定値は本書では一般化していない。

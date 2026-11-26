# `STRATA_STAGE_TRIM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

複数 GPU の layer split で、各 GPU がモデル全層分保持していた dense weight のうち、自分が実行する層の分だけを読み込む stage trim を選びます。空いた VRAM は expert cache などに使えるようになります。対象は `engine/src/program/generate.cpp` の CUDA/HIP 系エンジンと `engine/sycl/src/program/generate.cpp` の SYCL エンジンです。split がない単一 GPU では環境変数だけでは trim は実行されません（CUDA/HIP の自動 spill walk は別記）。`engine/src/program/generate.cpp:5827-5841,5951-5957`、`engine/sycl/src/program/generate.cpp:3086-3108`。

## 値と判定

両エンジンとも `std::getenv` で取得し、数値変換や真偽文字列の parse はしません。空でない文字列かつ文字列全体が厳密に `"0"` でなければ環境値を trim 要求として扱います。したがって `1`, `true`, `false`, `00`, `0abc`, 空白だけの値はいずれも env 判定上は要求ありです。空文字は要求なし、未設定も要求なしです。大文字小文字や数値としての妥当性は検査しません。CUDA/HIP では、これに加えて `"0"` だけを env による OFF として認識します。`engine/src/program/generate.cpp:5836-5841`、`engine/sycl/src/program/generate.cpp:3092-3095`。

| エンジン・条件 | unset / 空文字 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA/HIP, explicit split | env だけなら trim ON（default） | `1`, `true`, `0abc`; `--trim-stage-weights` でも ON | `0` は OFF。ただし `--trim-stage-weights` があれば CLI が優先して ON |
| CUDA/HIP, split auto | env だけなら通常 trim ON。値が unset/空であっても不足 VRAM 時の spill walk が later stage を trim する場合がある | 上記と同じ | `0` は通常 trim と spill walk の両方を抑止。`--no-trim-stage-weights` は通常 trim を OFF にするが、`STRATA_SPILL_OFF` が未設定なら不足時の later-stage spill trim は起こり得る |
| SYCL, explicit split または split auto | env だけなら trim OFF | 非空の任意文字列（`0` 以外）または `--trim-stage-weights` | unset、空文字、厳密な `0` |

CUDA/HIP では既定 `trim_stage_weights=true`、`--no-trim-stage-weights` は明示 OFF、`--trim-stage-weights` は明示 ON です。環境値 `0` は `--trim-stage-weights` が指定されていない場合に限り OFF として優先されます。CLI の parse は `engine/src/program/generate.cpp:4043,4120`、既定値と env/CLI の合成は同 `:1151-1155,5836-5841` にあります。SYCL は既定値が false で、`--trim-stage-weights` または env の非空かつ `!= "0"` が ON 条件です。同エンジンには `--no-trim-stage-weights` の parse がありません（同 `engine/sycl/src/program/generate.cpp:668,2039,3092-3102`）。

## 有効になる条件

- 実際の stage trim には複数 GPU の layer split が必要です。explicit split は split 境界が決まった経路で trim し、`auto` は trim 要求があれば later-stage weight の load を split 決定後まで遅らせます。CUDA/HIP は `engine/src/program/generate.cpp:5951-5957,5978-5982,6101-6102,6924-6945`、SYCL は `engine/sycl/src/program/generate.cpp:3102-3108,3126-3130,3703-3708,4210-4215`。
- CUDA/HIP の auto split では CUDA0 の arena が split 選択前に作られるため、stage trim が事前要求された場合でも CUDA0 は全層分を保持し、later stage が trim されます。explicit split では CUDA0 も自分の層範囲に trim されます（`engine/src/program/generate.cpp:5945-5957,5978-5982`）。
- CUDA/HIP の unset/空値や `--no-trim-stage-weights` で通常 trim を要求していなくても, auto split の spill walk は VRAM が不足する later card を trim することがあります。これは `STRATA_SPILL_OFF` または env 값 `0` で止まります。auto split 前の early walk にはさらに `STRATA_SPLIT_EARLY_OFF` も関係します（`engine/src/program/generate.cpp:5843-5856,6069-6102`）。
- SYCL の Intel setup は split の run config に `STRATA_STAGE_TRIM=1` を既定設定として追加しますが、`setdefault` のためユーザーが config env に指定した値は保持します（`engine/sycl/setup_intel.py:546-550`）。この設定補助を通さず直接 engine を起動する場合は、SYCL のコード既定値は OFF です。

## 実行時の詳細

環境値は `generate` 内の split/weight-loading 初期化中に読み取られます。CUDA/HIP は一度 `stage_trim_env` に保存して判定しますが、後続 spill 条件でも `getenv` を直接再評価します。SYCL は判定 lambda 内で一度読みます。いずれも request ごとの設定ではなく、既に起動したプロセスの環境変更を追う仕組みはありません（`engine/src/program/generate.cpp:5836-5841,5854-5856,6074-6075`; `engine/sycl/src/program/generate.cpp:3092-3102`）。

trim が走ると pack の `index.txt` から他 stage 所有の `blk.<layer>` dense weight 名を skip set に入れ、PLE weight は各 GPU に残します。CUDA0 は明示 split 時に `NativeDense::set_layer_range` も設定します。later stage は layer 範囲付きで weight load し、split search が cache sizing に利用できる VRAM を増やします（`engine/src/program/generate.cpp:5964-5982,6929-6945`; SYCL: `engine/sycl/src/program/generate.cpp:3112-3130,3703-3708`）。環境変数は token 選択や生成内容を直接指定せず、ロードする dense weight と cache に使える GPU memory の配分を変えます。

## ログと測定値

explicit CUDA0 trim 時は `strata generate: layer split: CUDA0 loads the dense weights of layers 0-%lld only` が stderr に出ます（`engine/src/program/generate.cpp:5978-5982`; SYCL 実装も `engine/sycl/src/program/generate.cpp:3126-3130`）。CUDA/HIP の auto spill walk が不足カードを trim する場合は `strata generate: short of GPU memory: ... each later card loads only the dense weights of its own layers (STRATA_STAGE_TRIM=0 keeps the copy)` を出します（`engine/src/program/generate.cpp:6085-6095`）。通常 trim の OFF を示す専用ログは確認できません。

`docs/MULTI_GPU.md:296` は `2x MI50 16 GB, Coder` で `STRATA_STAGE_TRIM=1` により expert VRAM cache が `8,819 -> 10,626`、decode が `39.2 -> 41.7 tok/s` と記録しています。これは当該資料の測定記録であり、他機種・モデルへの一般化はできません。現行コードのコメントは explicit trim の default を ON としています（`engine/src/program/generate.cpp:5829-5835`）。

## 根拠

- `engine/src/program/generate.cpp:1151-1155,4043,4120,5827-5841` — CUDA/HIP の既定値、値判定、CLI 優先順位。
- `engine/src/program/generate.cpp:5843-5856,5945-5957,5964-5982,6069-6102,6924-6945` — auto/explicit split、spill walk、trim の適用。
- `engine/sycl/src/program/generate.cpp:668,2039,3086-3108,3112-3130,3693-3708,4210-4215` — SYCL の既定値、値判定、split 後の trim。
- `engine/sycl/setup_intel.py:526-550` — Intel setup による split config の既定値。
- `docs/MULTI_GPU.md:296` — 条件付き測定記録。

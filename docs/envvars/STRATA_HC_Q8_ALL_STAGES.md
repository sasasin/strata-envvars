# `STRATA_HC_Q8_ALL_STAGES`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_HC_Q8` で有効になる hyper-connection の Q8_0 重みコピーについて、layer split 時に自 stage 外の layer 分まで各 GPU stage にコピーするかを切り替えます。未設定時は各 stage が担当する layer のコピーだけを作り、先頭文字が `1` の値を設定すると全 stage に全 layer のコピーを作る旧動作になります。Q8_0 自体を有効にする設定ではありません。

対象のコピー処理は `src/core/native_dense.cpp` の `NativeDense::load()` にあり、Q8 経路が有効な場合だけ実行されます。`hc_q8_name()` は `blk.<layer>` の6種の attention/FFN down・up・inject projection と、グローバルな `output_hc_down.weight` / `output_hc_up.weight` を対象名として認識します。stage フィルターは `blk.` tensor に適用されるため、グローバルな output mixer はこの変数にかかわらず対象 stage で処理されます（同ファイル `:91-97,446-460`）。

## 値と判定

値全体の parse や数値変換はせず、`getenv()` の結果が存在し、先頭文字が `'1'` かだけを見ます。stage-local フィルターはその否定です。

| 設定値 | stage-local フィルター | layer split 時の `blk.*` Q8_0 コピー |
|---|---|---|
| 未設定 | 有効 | この stage の layer 範囲だけをコピー |
| 空文字 | 有効 | この stage の layer 範囲だけをコピー |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 無効 | stage 範囲外を含む全 layer 分をコピー |
| その他（例: `0`, `true`, ` 1`） | 有効 | この stage の layer 範囲だけをコピー |

判定は `hc_q8_stage_local()` 内の `static const bool` に保存され、最初の呼び出し後にプロセス環境を変更しても再評価されません。読み取りは Q8_0 tensor を走査する `NativeDense::load()` 中、対象 tensor が現れた時点です（`src/core/native_dense.cpp:87-90,446-459`）。

## 有効になる条件

- `STRATA_HC_Q8` が有効であること。Q8_0 経路の処理は `if (hc_q8_env())` の内側です。`STRATA_HC_Q8` は明示値や backend・GPU architecture により別途判定されますが、この文書の変数がその判定を変更することはありません（`src/core/native_dense.cpp:46-85,446-448`）。
- native dense GGUF の読み込みがあること。通常は `--native` が native dense shard を設定し、`generate` が `NativeDense::load()` を呼びます。明示的な native dense 設定でも同じ呼び出し条件です（`src/program/generate.cpp:4385-4399,5192-5200`）。
- stage-local の範囲制限が意味を持つのは、複数 GPU の layer split で stage の layer 範囲が設定されるときです。trim された stage の範囲は `set_layer_range(lb, le)` に渡され、load 時には `outside()` と `in_range()` の両方で他 stage の layer が識別されます（`src/program/generate.cpp:5740-5752`; `src/core/native_dense.cpp:40-45,210,284-290,453-459`）。

Q8_0 の tensor は GGUF に存在し、名前・2次元形状が対象に合うものに限って候補となります。フィルターを外しても、GGUF に存在しない tensor を新規作成する設定ではありません（`src/core/native_dense.cpp:446-465`）。

## 実行時の詳細

`NativeDense::load()` は各 stage の GGUF shard を走査し、Q8_0 hyper-connection tensor を見つけると、既定では `outside(name)` または `!in_range(name)` の tensor をスキップします。`STRATA_HC_Q8_ALL_STAGES` の先頭文字が `1` ならこの条件全体を無効化し、対象である全 layer のコピーをその stage に割り当てます。コピー対象になった tensor は形状を照合し、デバイスメモリを確保して GGUF の Q8_0 payload を転送し、`WeightRef::hc_q8` に登録します。形状不一致や確保・転送失敗では load が失敗します（`src/core/native_dense.cpp:453-479`）。

この設定専用の stderr ログはありません。stage-local 時にスキップした数・容量は `STRATA_MANIFEST` が有効な場合に manifest の `dense_hc_q8_out_of_stage_not_copied` として記録されます。load が失敗した場合は呼び出し側が `strata generate: native dense projections: ...`、または layer split 時に `strata generate: layer split, CUDA%d native dense projections: ...` を stderr に出します（`src/core/native_dense.cpp:567-568`; `src/program/generate.cpp:5193-5196,5776-5779`）。

## 根拠

- 環境変数の読み取りと先頭文字判定、static cache: `src/core/native_dense.cpp:86-90`。
- コピー対象となる tensor 名: `src/core/native_dense.cpp:91-97`。
- Q8_0 tensor の絞り込み、stage 範囲フィルター、コピー処理: `src/core/native_dense.cpp:446-479`。
- layer 範囲の設定と stage ごとの読み込み: `src/program/generate.cpp:5740-5752,5776-5779`。
- native dense を有効にする呼び出し側: `src/program/generate.cpp:4385-4399,5192-5200`。

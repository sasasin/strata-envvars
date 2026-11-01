# `STRATA_KVA_ONLY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

KVA（近似 late-layer prompt read）が実行される chunk で、split 以降のどの種類の層を近似対象にするかを選びます。`gdn` は QSA ではない層、`qsa` は full-attention 層だけを選びます。選択された層では通常の層出力を作らない KVA 経路になり、MoE expert transfer の計画からも除外されます。選ばれなかった層は通常どおり処理されます。

この変数だけでは KVA は有効になりません。KVA の主スイッチ `STRATA_KVA` が有効で、対象 prompt が KVA の適用条件を満たす必要があります。

## 値と判定

`kva_config_from_env()` が `getenv()` で読み、空でない値を文字列全体で大文字小文字を区別して比較します。数値変換や部分一致はありません。

| `STRATA_KVA_ONLY` | 判定結果 |
|---|---|
| 未設定、空文字 | 既定の `all`。split 以降の全層を選択 |
| `gdn` | QSA ではない層だけを選択 |
| `qsa` | QSA 層だけを選択 |
| `all` | split 以降の全層を選択 |
| その他（`GDN`、` qsa`、`false` など） | `All` に戻り、split 以降の全層を選択 |

したがって無効な値によるエラーや警告はなく、実質的には既定値へ fallback します。`gdn` / `qsa` は層選択を変えますが、`STRATA_KVA` が未設定・空・先頭文字 `0` の場合、または KVA が当該 read を辞退した場合には選択結果は使われません。

根拠: `include/strata/prefill/kva.hpp:69-90,183-187`。QSA 層の判定は `include/strata/core/geometry.hpp:73-77`。

## 有効になる条件

- 通常実行では `STRATA_KVA` が空でない値かつ先頭文字が `0` 以外である必要があります。`STRATA_KVA_ONLY` は KVA を起動しません（`include/strata/prefill/kva.hpp:152-156`）。
- Metal build には KVA path がなく、KVA は無効になります。ヘッダーでは Metal 以外を KVA backend としますが、SYCL engine は独自の prompt path を使い KVA を適用しません（`include/strata/prefill/kva.hpp:43-49`; 適用条件の説明は `docs/KVA.md:99-104`）。
- `--batch` slot、layer split、`--peer-device` がある engine は起動時に KVA 全体を無効化します。DFlash2 prompt taps、画像 prompt、position 0 以外からの continuation、短い prompt、suffix を除く近似領域が足りない prompt も read 単位で KVA を辞退します（`src/program/generate.cpp:6263-6278`; `include/strata/prefill/kva.hpp:104-133`; `src/prefill/prefill.cpp:2947-2965`）。通常のモデル形状制限は 48 layers / 512 experts で、別形状は `STRATA_KVA_ANY_MODEL` が有効でない限り辞退します。
- CLI 引数や設定ファイルから `only` を上書きする経路は見つかりませんでした。KVA config は環境から組み立てられ、`kva_config()` の function-local static に初回取得後キャッシュされるため、実行中に環境を変えても反映されません（`include/strata/prefill/kva.hpp:149-195`）。

## 実行時の詳細

KVA が適用される chunk は、chunk の終端が完全計算 suffix の開始位置以前にあるものです（`src/prefill/prefill.cpp:3115-3123`）。各 chunk で split 以降の層を走査し、`STRATA_KVA_ONLY` の結果と層種別が一致した場合だけ `kva_layer` として扱います。`gdn` は `!is_qsa_layer(...)`、`qsa` は `is_qsa_layer(...)` に一致する判定です。`kva_layer` は既定の state-only 処理（または `STRATA_KVA_SKIP=moe` の場合の MoE 部分スキップ）に入り、全層モードでは同じ chunk の split 以降すべてが対象です（`src/prefill/prefill.cpp:3619-3629`）。

ストリーミング転送計画も同じ層選択判定を使い、選択層の expert transfer を queue に積みません（`src/prefill/prefill.cpp:3382-3394`）。従って `gdn` / `qsa` のどちらを選んでも、もう一方の層種別は通常処理と通常の転送計画を保ちます。

KVA が実行されたときの stderr 行には `gdn layers only` または `qsa layers only` が付きます。既定の全層モードではこの注記はありません（`src/prefill/prefill.cpp:5820-5831`）。KVA が辞退された場合は、明示的に `STRATA_KVA` を有効にしていれば辞退理由が `strata prefill: KVA configured but NOT applied: ...` と出ますが、`STRATA_KVA_ONLY` の不正値そのものを報告するログはありません（`src/prefill/prefill.cpp:5844-5856`）。

## 根拠

- 値の読み取り、完全一致、既定値への fallback、process cache: `include/strata/prefill/kva.hpp:69-90,183-195`
- QSA 層の定義: `include/strata/core/geometry.hpp:73-77`
- chunk の近似条件と層選択: `src/prefill/prefill.cpp:3115-3123,3619-3629`
- 選択層の expert transfer を省く処理: `src/prefill/prefill.cpp:3382-3394`
- 実行ログと辞退ログ: `src/prefill/prefill.cpp:5820-5856`
- KVA 全体の起動条件、既定値・説明との照合: `include/strata/prefill/kva.hpp:104-133`, `docs/KVA.md:43-58,99-117`

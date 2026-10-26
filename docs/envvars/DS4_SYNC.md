# `DS4_SYNC`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 専用エンジン（`strata-dsv41`）の decode で、routing 結果を GPU から mailbox 経由で service thread に送り、GPU が VRAM expert と shared expert を進めながら CPU 側 expert の応答を待つ経路を選ぶかどうかに関係します。`DS4_SYNC` が設定されていると、条件を満たす通常の単一 GPU decode と drafter ではこの非同期経路を選びません。環境変数の値を「同期モード」の数値や真偽値として parse する設定ではありません。

## 値と判定

| `DS4_SYNC` の状態 | 判定 |
|---|---|
| 未設定 | `sync_decode == false` |
| 任意の値を設定（`1`, `0`, `false`, 空文字を含む） | `sync_decode == true` |

実装は `std::getenv("DS4_SYNC") != nullptr` のみを評価します。文字列比較、数値変換、空文字の除外はありません。したがって `DS4_SYNC=0` も非同期経路を抑止します。値は `Model::Impl` のメンバー初期化時に読み取られ、モデルオブジェクトごとに保持されます。その後の環境変更では再評価されません。

## 有効になる条件

- この環境変数を読むコードは DeepSeek V4.1 専用の `strata-dsv41` エンジンにあります。CMake の `STRATA_BUILD_DSV41` は既定で `OFF` です。通常の `strata` 実行経路の設定ではありません。
- 通常の trunk decode は `plan_window()` が window の `T` と並列実行フラグ `par` を見て非同期 routing を選びます。`T <= DS4_ASYNC_T` かつ `par == false` のときだけ `DS4_SYNC` 未設定が非同期を許可します。`DS4_ASYNC_T` の既定値は 8 で、同じ `Model::Impl` 内で `std::atoi` により読み取られます。
- `par == true` の trunk decode は `wp.async = true` となるため、`DS4_SYNC` が設定されていても非同期 routing を使います。
- drafter の MTP block は `dp.async = !sync_decode && T <= async_max_t` で判定されます。ここには `par` による上書きがありません。
- `T > DS4_ASYNC_T` の window は `DS4_SYNC` が未設定でも非同期 routing を使いません。

## 実行時の詳細

通常 decode では `plan_window()` が各 window の計画に `wp.async` を設定します。これが真なら、各層は GPU で routing して mailbox に publish し、shared expert / VRAM expert の処理を進めつつ CPU lane の応答を待つ経路に入ります。偽なら GPU で routing した expert ID、重み、入力を host にコピーし、host が選択 expert を分類します。その間 GPU は shared expert を計算し、その後 `cudaEventSynchronize()` で routing 結果を待ってから expert の処理を続けます。つまりこの経路でも shared expert の処理は host 側の作業と重なり得ます。「同期」は全処理を一切重ねないという意味ではありません。

drafter の MTP block も同様に `dp.async` を設定しますが、その判定は `draft_()` 内で行われます。`DS4_SYNC` が設定されている場合、`T` が `DS4_ASYNC_T` 以下でも async mailbox sequence を発行せず、各層の `layer()` は非 async 側の処理を使います。

`DS4_SYNC` 自体の値に応じたログ出力は見つかりませんでした。関連する経路選択の根拠は `src/dsv41/ds4_model.cu:6750-6755,8458-8487,9051-9167` です。

## 根拠

- `src/dsv41/ds4_model.cu:983`: `std::getenv("DS4_SYNC") != nullptr` での存在判定。
- `src/dsv41/ds4_model.cu:987`: `DS4_ASYNC_T` の既定値 8 と整数変換。
- `src/dsv41/ds4_model.cu:6750-6755`: drafter の非同期判定と mailbox sequence 発行。
- `src/dsv41/ds4_model.cu:8458-8487`: trunk window の `par` 優先条件、`T` 上限と sequence 設定。
- `src/dsv41/ds4_model.cu:9051-9167`: async routing 分岐と非 async 側の host routing / GPU event wait。
- `CMakeLists.txt:797-810`: DeepSeek V4.1 の独立 executable と `STRATA_BUILD_DSV41` の既定 `OFF`。

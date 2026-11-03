# `FNX_QSA_DENSE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

FNX の CUDA QSA（query-based sparse attention）で選択処理を飛ばし、attention を全位置対象にします。通常の QSA は indexer の score から `cells` / `n_cells` を作り、その選択位置を attention に渡します。この変数が有効だと選択用出力の `n_cells` を `-1` にし、attention kernel が選択 list を使わず、行位置までの全所有 KV 位置を処理します。比較・診断用の分岐としてコメントされています。

## 値と判定

`src/split/src/env.hpp:33-40,51-52` の `env_flag` は `env_int(name, 0) != 0` です。`env_int` は未設定なら 0、設定時は符号付き 10 進整数を文字列全体で parse し、整数値が 0 以外なら有効です。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（既定値 0） |
| 空文字 | 無効値。`parse_whole` が失敗し、例外 `FNX_QSA_DENSE: '' is not a whole number` |
| `0`, `+0`, `-0` | 無効 |
| 0 以外の範囲内整数（例 `1`, `-1`, `2`） | 有効 |
| 空白、末尾文字、小数、整数範囲外など | 無効値。`env_int` が `std::runtime_error` を送出 |

境界は `strtoll` の `long long` 範囲です。空白は先頭・末尾とも許容されず、`parse_whole` は全体が整数であることと `ERANGE` でないことを確認します（同:15-21）。

## 有効になる条件

この設定の読み取りは `src/split/src/kernels.cu` の `FNX_KPART == 5` にコンパイルされる CUDA kernel launcher 内です（`kernels.cu:39-42,1283`）。一般の Strata attention 経路とは別の FNX split engine 実装です。

QSA を通る通常 attention 経路では `Engine::attention()` が `qsa()` を呼びます（`src/split/src/engine.cu:863-870`）。レーン別経路では `qsa_select_lanes()` が使われ、同関数は `attention` のレーン処理および MTP 処理から呼ばれます（同:1048-1069,1133-1154,1305-1323）。両 launcher に同じ設定判定があります。

値が有効でも、これら FNX QSA の CUDA 関数を実行しないプロセスでは読み取りも効果もありません。設定が CLI 引数や他の環境変数で上書きされる処理は見つかりませんでした。

## 実行時の詳細

`qsa()` は index/prep-pool kernel の後、選択 score/select kernel の前に関数ローカル `static const bool` として値を判定します（`src/split/src/kernels.cu:1362-1380`）。有効時は `n_cells` の各行を `0xff`（int の `-1`）で埋め、`ck_launch("qsa")` を行って戻ります。これにより通常の `k_idx_score` / `k_idx_select` は起動されません。

同様に `qsa_select_lanes()` はまず lane rows の null を検査し、続いて関数ローカル static で設定を読みます（同:1318-1332）。有効時は `n_cells` を `-1` にして launch check 後に戻り、score/select kernel を起動しません。設定が無効なら既定の選択 kernel が起動します。

attention 側の `k_attn_part` は `n_cells[t] >= 0` のときだけ選択 list を参照し、負値なら `kv_owned(row_pos(...), card)` を context 長として使います（`src/split/src/kernels.cu:523-536`）。従って `-1` は全ての過去位置という dense 側の sentinel です。

各関数の判定結果はそれぞれの `static const` に保持され、当該関数で初回評価後に環境を変更しても再評価されません。QSA が実行される前に値を設定してください。無効値の例外は環境 parse 時に発生します。Strata 独自の警告ログや設定値ログはこの分岐にはありません。CUDA launch 検査失敗時は `ck_launch` 経由の失敗となります。

## 根拠

- `src/split/src/env.hpp:15-21,33-40,51-52` — 整数文字列の全体 parse、未設定時既定値、0 以外判定。
- `src/split/src/kernels.cu:1318-1332` — lane QSA の判定、dense sentinel 設定、早期 return。
- `src/split/src/kernels.cu:1362-1380` — 通常 QSA の判定、dense sentinel 設定、selection kernel を省く分岐。
- `src/split/src/kernels.cu:523-536` — sentinel が負値の場合の attention context/list の選択。
- `src/split/src/engine.cu:863-870,1048-1069,1133-1154,1305-1323` — QSA と lane/MTP 呼び出し経路。


# `STRATA_SIDE_MIXER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

検証 window の GDN ゲートと QSA indexer の入力依存処理を、メインの CUDA stream と並行する side stream に移す。値 `1` はゲートと indexer の枝を使い、値 `2` はそれに加えて GDN ゲート射影と QSA query chain も別枝に移す。`0` ではこれらをメイン stream 上で従来順に実行する。ソースコメントは枝の有無で演算結果の算術は変わらないとしている（`engine/src/core/verify.cpp:272-274,2077-2082`）。

## 値と判定

`g_side_mixer()` は環境値を `std::atoi` で整数化してから `0..2` に clamp する。文字列全体の妥当性検査はなく、数値の後ろは無視される。したがって未設定は自動既定値に進む一方、空文字、`true`、`0anything`、`-1` は 0、`1junk` は 1、`2junk` や `3` は 2 になる。先頭空白は `atoi` が数値として読める場合に許容される。大文字小文字の区別は値の判定に関係しない（`engine/src/core/verify.cpp:275-292`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全 backend | backend 別の既定値へ進む | `1` または `2`（1..2へ clamp） | 0へ変換される値は枝なし |
| CUDA 明示値 | 該当なし | `1`, `2`, `1junk`, `2junk`, `3`（後二者は上限2） | 空文字、`0`, `0anything`, `true`, `-1` |
| HIP / Metal 明示値 | 既定は0 | `1`, `2`（同じ変換と clamp） | 0へ変換される値 |

`atoi` の整数表現範囲外の文字列について、C ランタイムが返す値を Strata は検証・規定していない。

unset 時の既定値は次のとおり。

- CUDA: 現在の GPU が compute capability 12.0 で `STRATA_SM120_PERF` が未設定または `atoi` の結果が非0なら 2、それ以外は 0（`engine/src/core/verify.cpp:278-292`; `engine/include/strata/core/sm120_series.hpp:32-38,60-61`）。
- HIP と Metal: 0（`engine/src/core/verify.cpp:278-280`）。明示値はこの fallback より先に返るため、ソース上は明示的な `1` / `2` を受け付ける。
- CUDA の起動時既定値表は、全可視 CUDA GPU が同一 compute capability の場合に適用される。未設定なら sm_86、sm_89、sm_120、sm_70、sm_60 で mode 2 を環境へ設定する。sm_89 / 70 は `STRATA_DEFAULTS=026` で表が無効になり、sm_120 は `STRATA_SM120_PERF=0` または `STRATA_DEFAULTS=026` で無効、sm_70 は `STRATA_SM70_PERF=0` または `STRATA_DEFAULTS=026` で無効、sm_86 / 60 は各 `STRATA_SM86_PERF=0` / `STRATA_SM60_PERF=0` で無効。sm_121 も同一世代表で `STRATA_SM121_PERF=0` / `STRATA_DEFAULTS=026` で無効（`engine/src/core/nv_defaults.cpp:37-42,75-83,104-107,136-141,164-180,222-233`; `engine/src/program/generate.cpp:4421-4449`）。
- 既定値表が値を設定するのは対象名が環境に存在しない場合だけで、空文字を含む利用者設定は保持される。したがって明示した `STRATA_SIDE_MIXER=0` は既定値表にも優先する（`engine/src/core/nv_defaults.cpp:227-234`）。

注: `STRATA_DEFAULTS=026` は sm_120 の既定値表を省くが、それだけでは `g_side_mixer()` の直接 fallback を無効にしない。sm_120 の暗黙 mode 2 を止める条件は `STRATA_SM120_PERF=0`、または明示 `STRATA_SIDE_MIXER=0` である（`engine/src/core/nv_defaults.cpp:104-107`; `engine/src/core/verify.cpp:275-292`）。

## 有効になる条件

- mode 1 / 2 の枝は Verifier の CUDA/HIP window 初期化と `record_window` 経路で使われる。Metal は window 初期化後に Metal engine へ戻るため、この CUDA/HIP の枝経路を通らない（`engine/src/core/verify.cpp:978-993,1404-1412`）。
- batch window では `STRATA_BATCH_SIDE_MIXER` も真である必要がある。これは未設定・空文字なら off、値の先頭文字が `'0'` 以外なら on とする判定で、`STRATA_SIDE_MIXER` の数値判定とは異なる。off の場合、batch 内のゲート/indexer/query 処理は side branch に移らない（`engine/src/core/verify.cpp:336-339,370-372,1503-1515`）。
- `STRATA_SIDE_MIXER=2` の追加 projection/query 枝は、batch では `STRATA_BATCH_SIDE_MIXER` が on の場合に限り使われる（`engine/src/core/verify.cpp:1504-1507`）。
- `STRATA_DF_BRANCH` の別の枝は `STRATA_SIDE_MIXER` が有効なとき無効化される。コード上の条件は単一 group、非 batch、非 profiler かつ `!side_mixer` である（`engine/src/core/verify.cpp:1548-1551,1610`）。
- CUDA の起動時既定値表は全可視 GPU が同一世代のときのみ適用される。混在世代時にはこの表による mode 2 の設定はない。sm_120 を含む混在構成では、未設定だった `STRATA_SM120_PERF` を `generate.cpp` が `0` にして既定 fallback を止める（`engine/src/program/generate.cpp:4427-4459,4463-4469`）。利用者が `STRATA_SIDE_MIXER` を明示すれば `g_side_mixer()` の明示値判定が fallback より先に返る（`engine/src/core/verify.cpp:275-280`）。

## 実行時の詳細

値の解析結果は `g_side_mixer()` の関数内 `static` に保存され、プロセス中に環境値を変更しても再読込されない。CUDA で環境値が未設定の場合はデバイス index ごとにも能力値の判定を cache し、compute capability の問い合わせに失敗した場合はそのデバイスの既定を 0 とする。通常の起動では `apply_nv_defaults()` が起動時に環境へ既定値を入れ、Verifier 初期化時に `g_side_mixer()` が評価される（`engine/src/core/verify.cpp:275-292,1404-1412`; `engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:222-234`）。

mode 1 以上では Verifier 初期化時に side stream と対応 event を作成する。mode 1 では GDN gates、QSA indexer key/snapshot/append/query/select を `side_` で実行する。mode 2 はそれらに加えて GDN gate projection と QSA query chain を `side2_` で実行し、後続処理が event を待つ。値 0 なら処理はメイン stream `cs` 上に残る（`engine/src/core/verify.cpp:1404-1412,1897-1920,2061-2082,2318-2335`）。

side stream または event の作成に失敗すると初期化は `false` を返し、`err` に `verify: the mixer branch's stream / events could not be created` を設定する。枝の event 操作にも失敗経路があり、例として `verify: the GDN gates' branch could not join`、`verify: the indexer's branch could not join`、`verify: the queries' branch could not join` が設定され、window capture は失敗を返す（`engine/src/core/verify.cpp:1404-1412,1903,1969-1975,2326,3280-3285`）。

## ログと測定値

CUDA の既定値表が実際に値を追加した場合、stderr に `strata: sm_...: ... switches on by default ...` の行が出て、追加した switch 名の一覧には prefix を除いた `SIDE_MIXER` が出る。利用者が明示値を設定して表が何も追加しない場合、この行は出ない（`engine/src/core/nv_defaults.cpp:222-255`）。

window ごとの `side_mixer` と `side_proj` の実値は dispatch 統計に記録される。dispatch 統計は既定で有効だが、`STRATA_DISPATCH_STATS=0` で無効にできる。記録自体は通常の stderr ログではなく、`STRATA_DISPATCH_REPORT=<path>` の report または CLI `--stats` の出力で観測する（`engine/src/core/verify.cpp:1543-1548`; `engine/include/strata/core/dispatch_stats.hpp:9-12,107-119`）。

`docs/DETAILS.md:1298,1486-1489` と `engine/include/strata/core/sm120_series.hpp:4-20` は mode 1/2 の意図や機種別の既定値・測定を記載している。上記の動作説明は実装分岐に基づく。ここでは資料中の性能測定値を一般化して記載しない。

## 根拠

- 値の読み取り、変換、clamp、backend fallback、GPU ごとの既定値: `engine/src/core/verify.cpp:272-292`
- sm_120 性能スイッチ判定: `engine/include/strata/core/sm120_series.hpp:32-38,60-61`
- GPU 世代ごとの起動時既定値表と環境への設定: `engine/src/core/nv_defaults.cpp:37-42,75-83,104-107,136-141,164-180,222-255`
- 既定値設定の呼び出し、混在世代の扱い: `engine/src/program/generate.cpp:4421-4449,4450-4469`
- batch / DF branch 条件と dispatch 記録: `engine/src/core/verify.cpp:370-372,1503-1515,1543-1551,1610`
- side branch の実処理と失敗経路: `engine/src/core/verify.cpp:1404-1412,1897-1920,1962-1975,2077-2082,2318-2335,3280-3285`
- 計測報告の出力条件: `engine/include/strata/core/dispatch_stats.hpp:9-12,107-119`

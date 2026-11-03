# `FNX_LANES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`FNX_LANES` は、Flash-Next 用の `split_fnx_run` 診断・テスト実行ファイルが Engine を作るときに、K/V pool に追加 lane 用のページをどれだけ初期確保するかを指定します。lane 数そのものを作成する設定ではありません。lane 0 は常に存在し、追加 lane は `bench_step` の `L` 引数に応じて `Engine::add_lane()` が作ります。

この読み取りは `src/split/tools/fnx_run.cpp` にあり、同ファイルの `main` を持つ CMake ターゲット `split_fnx_run` に組み込まれます。通常の `sfnx` サーバー経路がこの環境変数を読む実装は見つかりません。

## 値と判定

`fnx::env_int("FNX_LANES", 1)` が `env.hpp` の `env_int` を通じて値を読みます。環境変数が未設定なら既定値は `1` です。設定値は符号付き 10 進整数として文字列全体を parse します。先頭の `+` / `-` は許されますが、空文字、空白、数字以外の末尾、`long long` 範囲外は無効です。

| 入力 | 結果 |
| --- | --- |
| unset | `1` |
| `1`, `+3` | それぞれ `1`, `3`。値に応じて追加ページを計算 |
| `0`, 負値 | parse は成功するが、Engine の追加ページ計算では lane 数を最低 `1` として扱うため追加ページなし |
| 空文字、`2x`、空白を含む値、`long long` 範囲外 | `env_int` が例外を送出し、Engine 初期化に失敗 |

読み取った `long long` は Engine に渡す前に `int` へキャストされます。コードに `FNX_LANES` 固有の範囲検証や上限 clamp はありません。

## 有効になる条件

- 対象は `src/split/CMakeLists.txt` が定義する CUDA ターゲット `split_fnx_run` です。ビルド時に `FNX_NCARD`、`FNX_ARCH`、`FNX_27B=0`、`FNX_HOSTRING=1` が定義されます。
- `fnx_run_cmd()` は `exact` / `read` / `batch` / `compare` / `decode` / `bdecode` / `cache2` の lab mode を Engine 作成前に別経路へ返します。そのため、これらの mode では `FNX_LANES` を読みません。他の通常 mode では `Engine` 作成時に読みます。
- 追加確保ページ数は `(max(lanes, 1) - 1) * lane_block_pages()` です。`lane_block_pages()` はモデルの層・カード構成に応じて lane の状態領域をページ換算します。既定値 `1` は lane 0 分を超える追加ページを要求しません。
- `FNX_MAX_CTX` は同じ Engine 作成時に別途読み取られ、K/V pool の文脈用ページ数を決めます。したがって `FNX_LANES` は `FNX_MAX_CTX` を上書きせず、追加 lane 用ページを context 分に加算します。
- `bench_step` の CLI 引数 `L` が実際に作る lane 数を決めます。`FNX_LANES` は `L` に対する硬い上限ではありません。設定値が小さくても、既存の free pages に連続領域があれば追加でき、領域が取れなければ失敗します。設定値を大きくしても lane を自動作成せず、未使用の追加ページを K/V pool に確保します。

## 実行時の詳細

通常 mode では、引数の妥当性確認とモデル読み込みの後、`fnx_run_cmd()` が Engine を作る際に `FNX_LANES` を一度読みます。`env_int` は static cache を使わず、その呼び出しで `std::getenv` を実行します。プロセス内で環境を後から変更する場合の再評価経路はこの呼び出しにはありません。

Engine は context 用ページに追加 lane 用ページを加えた pool を構成し、空き VRAM 等に基づくページ数の制限を適用します。`bench_step` は `L` が 1 を超えると `add_lane()` を繰り返し、free pages 内に lane 状態用の連続ページがない場合、arena の追加領域を使えなければ `add_lane: no run of ... free pages in the K/V pool` 例外になります。lane の確保は逐次で、環境変数値と CLI 引数 `L` の大小だけで成功・失敗が決まるわけではありません。

無効な整数は `FNX_LANES: '<値>' is not a whole number` の例外になります。`split_fnx_run` の `main` は例外を `fnx_run: <例外文>` として stderr に出し、終了コード `1` を返します。lane の追加に失敗した場合も同じ catch 経路です。成功時に `FNX_LANES` 固有のログはありません。

## 根拠

- `src/split/tools/fnx_run.cpp:958-988,1364-1373` — lab mode の早期 return、通常 mode での環境値読み取り、既定値、`int` キャスト、および例外時の stderr / 終了コード。
- `src/split/src/env.hpp:15-21,33-40` — 符号付き 10 進数の全体 parse、unset 時の既定値、無効値の例外。
- `src/split/src/engine.cu:31-36,70-80` — Engine の構築、`max(lanes, 1)` による最低 lane 数、および追加ページの算出。
- `src/split/src/engine.cu:695-706,709-730` — lane 状態領域のページ算出、追加 lane の連続領域確保、および不足時の例外。
- `src/split/tools/fnx_run.cpp:1239-1248` — `bench_step` の `L` 引数と `add_lane()` による lane 作成。
- `src/split/CMakeLists.txt:153-165` — `split_fnx_run` がテスト driver であること、CUDA 実行ファイルとビルド定義。

索引 `docs/envvars/000_envvers.md` には `FNX_LANES` が候補としてあります。Strata ソースに実際の読み取り箇所が確認できたため、候補と実装の食い違いはありません。`docs/DETAILS.md` にはこの名前の説明が見つからず、ここではコードで追えた動作だけを記載しています。

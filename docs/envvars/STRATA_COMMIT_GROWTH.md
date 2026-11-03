# `STRATA_COMMIT_GROWTH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows の page file が現在のサイズから拡張できる見積もりを、DS4 (DeepSeek-V4.1-Flash) の commit 余力計算に加算します。環境変数を `0` として扱う値にすると、この追加見積もりを無効にできます。Windows の実 commit 量や page file 設定そのものは変更しません。

このコードは `STRATA_BUILD_DSV41` が有効なときに作られる独立実行ファイル `strata-dsv41` の経路にあります。同変数の実際の読み取りは `include/strata/platform/commit.hpp` の1か所で、Strata の一般実行ファイル、サーバー起動 Python、他の同梱ツールからの読み取りは見つかりませんでした（`CMakeLists.txt:931-945`）。

## 値と判定

Windows ビルドで `commit_growth()` が呼ばれるたびに `getenv()` で読み、`std::atoi()` の結果だけを判定します。文字列全体の厳密な数値 parse やエラー報告はありません。

| 値 | `atoi` の結果 | 動作 |
|---|---:|---|
| 未設定 | 判定なし | page file 設定などから拡張可能量を計算する |
| `0`、空文字、数字で始まらない文字列（例: `false`） | 0 | 計算を打ち切り、追加量 0 を返す |
| 先頭の整数部分が 0 以外（例: `1`, `2`, `-1`, `1junk`） | 非0 | 通常どおり計算する |
| 先頭の整数部分が 0（例: `0`, `0junk`, `0.5`） | 0 | 追加量 0 を返す |

`atoi` は先頭の空白と符号を許し、数字列の後ろは判定に使いません。したがって `false` は「無効な設定値」として警告されず、変換結果 0 により機能を無効にします。Windows 以外ではこの環境変数の読み取りコード自体がコンパイルされず、関数は常に 0 を返します。根拠: `include/strata/platform/commit.hpp:27-33,79-82`。

## 有効になる条件

- **OS:** `_WIN32` のビルドだけで値を読み、page file の拡張可能量を調べます。Windows 以外では追加量は常に 0 です。
- **実行経路:** CMake の `STRATA_BUILD_DSV41` が有効で、`strata-dsv41` の DS4 モデル配置・コピー容量の評価が `os::commit()` を通る場合に使われます。既定では DS4 ターゲットは OFF です（`CMakeLists.txt:931-945`）。
- **GPU 状態:** Windows での GPU expert 配置上限としては、統合 GPU（またはテスト用 `DS4_COMMIT_CAP_GB` 設定時）の commit 上限に入ります。一方、CPU lane expert のコピー可能量を決める `commit_room()` にも使われ、そこでは commit 課金 GPU の有無にかかわらず Windows の上限として評価されます（`src/dsv41/ds4_model.cu:1541-1559,5393-5397,5867-5873,6469-6484`）。
- CLI 引数や別環境変数で `STRATA_COMMIT_GROWTH` の値が上書きされる箇所はありません。`DS4_COMMIT_CAP_GB` は GPU の commit 課金判定・容量を変える別の分岐であり、この変数の判定値を変換しません。

## 実行時の詳細

`commit_growth(ram_total)` は Windows の `PagingFiles` レジストリ値を `RegGetValueW` で読み、各 page file の現在サイズ、ボリューム空き容量を調べます。自動管理の page file は、Windows から見える RAM の3倍（最低4 GiB）とボリュームの8分の1の小さい方まで拡張できるものとして計算します。固定サイズの page file は設定上限までを候補にします。いずれもボリューム空き容量から容量の10%を残す分を差し引いて上限を取り、実サイズからの増分を合算します。設定値を `0` と判定した場合はこれらの問い合わせを行いません（`include/strata/platform/commit.hpp:27-78`）。

`os::commit()` は Windows の `GlobalMemoryStatusEx` が成功した場合、現在利用可能な commit (`ullAvailPageFile`) にこの増分を足して `avail` にします（`src/dsv41/ds4_os.hpp:656-674`）。`commit_room()` はこの `avail` から他プロセス用の余裕（RAM の10%または8 GiBの大きい方）を引き、0未満を0に丸めます（`src/dsv41/ds4_model.cu:1535-1545`）。関数内に `static` cache はなく、`commit_room()` が呼ばれるたびに `os::commit()`、さらに環境変数判定と Windows 情報取得が行われます。プロセス起動後に環境を書き換えた場合も、後続呼び出しで再読込されます。

この容量は、統合 GPU では `place_experts()` の GPU expert budget を抑え、容量を超える expert を GPU に置かない判断に使われます。抑制により expert が GPU に置かれなかった場合は stderr に `ds4: WARNING: ...` の警告と page file の案内を出します（`src/dsv41/ds4_model.cu:5393-5397,5435-5444,5478-5489`）。CPU lane の expert コピーでは `--mmap-experts` のモードと実際の空き RAM との小さい方の上限に入り、収まらない場合は全量コピーを選ばず、または `--mmap-experts off` でも収まる分だけをコピーして残りを model file から読みます。関連ログは `src/dsv41/ds4_model.cu:5867-5889` にあります。`STRATA_COMMIT_GROWTH=0` やレジストリ等の取得失敗は追加余力を0にするため、これらの容量判定がより小さくなり得ます。

DLL のロード、レジストリ取得、値の取得のいずれかに失敗した場合も `commit_growth()` は0を返します。これらの失敗に対する専用ログやプロセス終了処理はありません（`include/strata/platform/commit.hpp:36-49`）。変数自身の無効値に対する警告もありません。

## 根拠

- 環境変数の唯一の読取箇所、Windows 条件、既定計算、失敗時の戻り値: `include/strata/platform/commit.hpp:27-82`
- commit の `avail` への加算: `src/dsv41/ds4_os.hpp:656-674`
- commit 余力の算出と統合 GPU の判定: `src/dsv41/ds4_model.cu:1535-1559`
- GPU expert 配置予算と観測可能な警告: `src/dsv41/ds4_model.cu:5393-5444,5478-5492`
- CPU lane expert コピー予算・ログ: `src/dsv41/ds4_model.cu:5867-5889,6469-6484`
- `docs/DETAILS.md:251` は Windows の available commit が resident budget を制限する一般説明を記載していますが、`STRATA_COMMIT_GROWTH` や DS4 の page file 拡張見積もりの説明はありません。ここでは上記の現行ソースで確認できる範囲を記載しました。

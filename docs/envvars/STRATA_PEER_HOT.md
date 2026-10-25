# `STRATA_PEER_HOT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--peer-device N` で使う peer GPU の expert cache に、頻度 profile 上位の expert をどの程度優先して回すかを調整します。値 `f` は上位候補のうち peer 側へ回す割合として使われ、profile の順番を並べ替えます。expert を直接選択・転送する処理は `PeerExperts::open()` が行い、この変数自体が cache 容量や peer device を設定するわけではありません。

## 値と判定

profile を読み込んだ直後、`o.peer_device >= 1` のときだけ `std::getenv()` で読みます。`STRATA_PEER_HOT` が未設定なら `f = 0.45`、設定されていれば `std::atof()` の結果です。文字列全体の検証はなく、数値として読める先頭部分を使います（例: `0.3junk` は `0.3`、`junk` と空文字は `0`）。判定は厳密な `f > 0.0 && f < 1.0` なので、0 以下、1 以上、NaN は並べ替えません。

| `STRATA_PEER_HOT` | 結果 |
|---|---|
| 未設定 | `f = 0.45` で並べ替えを試みる |
| `0`、空文字、数値で始まらない文字列 | `f = 0` となり並べ替えなし |
| `0 < f < 1` として読める値 | 並べ替えを実行 |
| `1`、負値、NaN、無限大など | 範囲条件を満たさず並べ替えなし |

どこまでの順位を候補にするかは別変数 `STRATA_PEER_HOT_AT` で決まります。未設定時は 8700、設定時は `std::atoll()` の結果を `size_t` に変換した後、profile の件数で上限を取ります。したがって空文字・数値で始まらない文字列・`0` は 0 件となって処理を無効にします。負値は符号なし変換で大きな値になり、profile 全件まで上限処理されます。`at` が 0 件なら、`f` が範囲内でも何も変更しません。

## 有効になる条件

- `--peer-device` が 1 以上であること。既定の peer device は無効（負値）です。
- `--expert-profile` から profile を読み込めること。読み込み失敗時はエラーで終了し、変数の評価には到達しません。
- `f` が 0 より大きく 1 より小さいこと、および `at > 0` であること。
- profile の並べ替え後、peer cache は主 GPU が保持していない順に空き VRAM（reserve を差し引いた分）へ候補を格納します。主 GPU が候補をすべて保持する場合、この変数で並べ替えた候補が peer に入るとは限りません。

`--peer-device` は `--layer-split` および `--expert-cache-device1..3` と併用できず、併用時は起動時検証で終了します（`src/program/generate.cpp:2607-2614`）。peer cache の初期化には profile、主 GPU の expert cache、expert source も必要です（同: `5450-5459`）。

## 実行時の詳細

並べ替えでは profile 内の順位 `r`（0 始まり）について、`int64((r+1)*f) > int64(r*f)` となる要素を `moved` に、その他を `keep` に分けます。候補範囲は `at = min(profile.size(), STRATA_PEER_HOT_AT)` です。出力順は `keep`、範囲外の順位 `at` から `fill-1`、`moved`、残りの順位で、`fill = min(profile.size(), at + moved件数)` です。つまり `f` は厳密な cache 割合指定ではなく、この規則で順位を再配置する入力です。実際に peer が受け取る expert 数は主 GPU の cache 内容と peer の空き容量・`--peer-slots` にも左右されます。

処理は起動時の profile 読み込み箇所で直接評価され、値を static cache したり、リクエストごとに読み直したりしません。プロセス起動後の環境変更はこの選択に反映されません。有効な並べ替えでは stderr に `strata generate: STRATA_PEER_HOT %.2f: %zu of the first %zu ranked pairs moved behind rank %zu (the peer's)` が出ます。無効値ではこのログも並べ替えもありません。

同じ処理が `sycl/src/program/generate.cpp` にもありますが、SYCL の `PeerExperts::open()` は `--peer-device: the second-GPU expert tier is not ported to SYCL yet` を返します。そのため SYCL で peer device を指定した場合、profile 並べ替えログが出ることはあっても peer tier の初期化は失敗します（`sycl/src/core/peer_experts.cpp:19-22`）。

## 根拠

- 読み取り、既定値、範囲、並べ替え、stderr ログ: `src/program/generate.cpp:3500-3531`。同等の SYCL 実装: `sycl/src/program/generate.cpp:3372-3403`。
- profile 読み込みの前提と失敗時の終了: `src/program/generate.cpp:3489-3495`。
- peer cache が主 cache にない候補を順に選び、空き容量・reserve・slot 上限で止める処理: `src/core/peer_experts.cpp:135-153`。宣言上の説明: `include/strata/core/peer_experts.hpp:42-46`。
- peer device の CLI 既定値と profile 引数: `src/program/generate.cpp:2099-2106`。併用禁止: 同 `2607-2614`。
- `docs/SECOND_GPU.md` の Peer tier 節は、peer が profile 順のうち primary が保持しない候補を取る仕組みを説明していますが、`STRATA_PEER_HOT` の設定値や順位変更規則は記載していません。上記の具体的な値判定・動作はソースコードに基づきます。
- 実装コメントには既定 `0.45` と「`0.3–0.6` は `0` より良かった」という測定に関する記述があります（`src/program/generate.cpp:3505`）。条件や測定結果を示す資料を確認できなかったため、性能向上の事実としては採用していません。

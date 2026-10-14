# `STRATA_METAL_FUSE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有ソース。候補名の完全一致検索では、実装上の読み取り箇所は Metal decode window の1か所だった。

## 役割

Metal エンジンの decode window で二つの処理を融合する設定です。既定で有効です。

1. GDN step が出力を後続の行列演算向けに prepare した activation plane へ直接書き、別 dispatch の `xprep` を省きます。
2. window の終端位置が 2051 以下なら、QSA の score と top-k による index 選択を省きます。この範囲ではセル index の配列が初期状態の identity 配列のままであることを利用します。

## 値と判定

環境変数の文字列全体を `"0"` と比較します。数値 parse や前後空白の除去はありません。

| 値 | 結果 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効 |
| 文字列が正確に `0` | 無効 |
| `00`、`0foo`、`false`、`1` など、それ以外 | 有効 |

## 有効になる条件

- この読み取りは `metal/src/engine/window.cpp` にあり、Metal エンジンの window 経路に限られます。`window_create()` が window を作り、`window_init()` は `--native SHARD1` のモデル shard が設定されている場合に初期化します。
- GDN の `xprep` 省略は GDN 層で処理されます。QSA の score/top-k 省略は各 window の終端 `pos0 + Tn`（layer 内では `pos0 + ntok`）が `<= 2051` の場合だけです。それより先では `STRATA_METAL_FUSE` が有効でも選択処理を実行します。
- したがって値を無効にすると GDN の direct prepare と QSA 選択省略の両方が止まります。window 経路自体が使われない実行にはこの変数の効果はありません。

## 実行時の詳細

値は `Window` オブジェクトのメンバー初期化時に読み取られます。実装はプロセス内で decode window を一つ共有します。生成済み window が存続している間に環境を書き換えても設定は変わりません。window を破棄して再生成した場合は、新しいオブジェクトの構築時に読み直されます。

GDN 層では有効時に kernel の `plane` 引数を `MAXT * 6144` とし、出力先に `XY_` を渡します。kernel は GDN 出力に加え、activation の各 plane と per-16 sums を書き込みます。無効時は `plane=0` で `yg_` に出力し、その後 `xprep` dispatch を追加して `XY_` を作ります。いずれも続けて `ssm_out` の GEMV に渡されます。

QSA 層では score と top-k dispatch の追加を `sel` で制御します。`qsa_prep`、`qsa_attn`、`qsa_merge` はこの条件に関わらず構成されます。初期化時に `qids_` は identity 配列として作られています。選択を実施した後に再び選択省略可能な window に入ると、`qdirty_` に基づき `qids_` を identity に戻してから score/top-k を省略します。

`docs/MAC.md` は `STRATA_METAL_FUSE=0` を「二つの decode fusions」を止める設定として記載し、同じ token で遅くなると説明しています。ここではその資料の記載を引用しており、独自の性能測定は行っていません。

## 根拠

- 環境変数の完全一致判定、両処理の概要: `metal/src/engine/window.cpp:238-242`。
- Metal window の生成・共有・モデル shard 条件: `metal/src/engine/window.cpp:2455-2481`。
- GDN dispatch の `plane`、出力先、無効時の `xprep`: `metal/src/engine/window.cpp:675-690`。
- kernel が `plane` 有効時に各 plane と sums を書く処理: `metal/kernels/gdn.metal:125-165`。
- QSA score/top-k dispatch の条件と常時追加される attention/merge: `metal/src/engine/window.cpp:717-757`。
- window 単位の QSA 選択条件と `qids_` の復元: `metal/src/engine/window.cpp:976-984`。
- identity index の初期化: `metal/src/engine/window.cpp:476-477`。
- 資料の説明: `docs/MAC.md:183-193`。

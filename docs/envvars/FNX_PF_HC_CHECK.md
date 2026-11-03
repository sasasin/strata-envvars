# `FNX_PF_HC_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

split engine の prompt prefill で、hyper-connection の inject 行を二つのカーネル経路で計算して照合する診断用スイッチです。既定では比較を行いません。モデル計算を選ぶ CLI 引数や通常の実行設定ではなく、比較処理を追加して stderr に差を出します。

## 値と判定

値の文字列・数値への変換はありません。`std::getenv(...) != nullptr` で設定の有無だけを判定します。

| 環境変数の状態 | `check` | 結果 |
|---|---:|---|
| 未設定 | false | 比較しない |
| 設定あり（空文字を含む） | true | `w_inj` が non-null の呼び出しで比較する |

したがって `0`、`false`、空白なども、変数が存在すれば有効です。無効値の parse や fallback はありません。CLI 引数など別設定との優先順位も実装されていません。

## 有効になる条件

- split engine の CUDA または HIP ビルドに含まれる prompt prefill 経路で使われます。`prefill.cu` は split engine のソース一覧に入り、HIP ビルドでは HIP 言語としてコンパイルされます（`src/split/CMakeLists.txt:64-79`）。
- `pf_hc_read()` が呼ばれ、かつ `w_inj` が non-null である必要があります。MTP draft layer の呼び出しは `w_inj=nullptr` を渡すため、そこで設定値が true でも比較は行いません（`src/split/src/prefill.cu:947-965`）。通常の prompt pass は layer の `hc_inj` 重みを渡します（`src/split/src/prefill.cu:1197-1198,1256-1261,1265-1275`）。
- 上記の `check` 自体は関数内 static 変数です。最初の `pf_hc_read()` 呼び出しで設定の有無を一度だけ読み、その結果をプロセス内で保持します。最初の呼び出しで `w_inj` が null でも値は確定するため、その後に環境を変更しても反映されません（`src/split/src/prefill.cu:451-453,469-472`）。

## 実行時の詳細

通常の読み取りでは `k_hcb_prep` が inject 行を `inject` に書き、続く `k_hcb_mixinj` は `w_inj=nullptr` で mixed 出力を作ります。比較が有効で `w_inj` がある場合、追加で GPU バッファを確保し、同じ mixinj カーネルに `w_inj` を渡して参照 inject 行を作ります。二つの行列を host にコピーして stream を同期し、各要素の差の最大絶対値と参照値の最大絶対値を計算して、次の形式で stderr に出します。

```text
hc check: inject largest difference <差> of largest value <参照値の最大絶対値>
```

差に対する許容値判定、警告、差に応じた分岐や終了処理はありません。比較結果はログに限られ、比較用出力は scratch に書かれるため、通常の `mixed` / `inject` 出力を置き換えません。一方、比較に伴う追加 GPU メモリ確保と stream 同期が発生します。確保・コピー・同期などの CUDA/HIP API エラーは `ckc()` が `prefill: hc check: ...` の `std::runtime_error` にします（`src/split/src/pf_common.cuh:27-29`; 呼び出し箇所は `src/split/src/prefill.cu:475-481`）。

## 根拠

- 候補名の Strata 内全参照は `src/split/src/prefill.cu:470-471`（意図のコメントと実際の `getenv` 読み取り）です。名前を動的に渡す helper 経由の参照はありません。
- 設定有無の static 判定、`w_inj` 条件、追加計算、ログ: `src/split/src/prefill.cu:469-487`。
- inject 行の通常計算と hyper-connection の処理: `src/split/src/prefill.cu:91-145,150-180,451-453`。
- prefill の呼び出し経路: `src/split/src/prefill.cu:982-1038,1197-1198,1256-1275`。
- 候補一覧には `FNX_PF_HC_CHECK` があります（`docs/envvars/000_envvers.md:568`）。`docs/DETAILS.md` および関連資料にはこの名前の追加説明は見つからず、本書の挙動説明は上記ソースを根拠にしています。

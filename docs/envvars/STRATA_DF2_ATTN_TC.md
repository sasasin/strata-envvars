# `STRATA_DF2_ATTN_TC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA 版 DFlash2 の attention で、sm_80 以上向け BF16 tensor-core kernel の選択を止めるスイッチです。値の先頭文字が `0` なら通常の `attn_part_kernel` を選びます。それ以外の場合も NVIDIA GPU の compute capability major が 8 未満なら通常 kernel です。tensor-core kernel を選んだ後も attention の分割結果を `attn_merge_kernel` で統合します。DFlash2 の起動自体や drafter の選択は制御しません（`engine/src/kernels/cuda/dflash2.cu:1696-1724`）。

この環境変数を読むのは、HIP コンパイルではない CUDA 実装だけです。HIP の AMD 分岐は `STRATA_DFLASH_WMMA`、`STRATA_GFX11_DEFAULTS`、`STRATA_GFX11_WMMA_DEFAULTS` と gfx11 判定で別の WMMA kernel を選び、この変数を参照しません（`engine/src/kernels/cuda/dflash2.cu:542-560,1698-1718`）。したがって設定一覧の「NVIDIA and AMD」という記載のうち AMD への適用は、この commit の実装では確認できません（`docs/SETTINGS.md:367`）。

通常の DFlash2 実行では drafter の各層の block 処理から attention 関数を呼びます。アプリケーション側で DFlash2 が選択・利用可能であることが前提です（`engine/src/core/dflash2.cpp:539-568`、`engine/src/program/generate.cpp:6477-6503,8195-8255`）。

## 値と判定

CUDA 実装は `std::getenv` の結果が null かを確認したうえで、設定値の **先頭 1 文字だけ**を比較します。値全体の parse、空白除去、大文字小文字変換、数値妥当性確認はありません（`engine/src/kernels/cuda/dflash2.cu:1703-1713`）。

| 条件 | unset | 有効になる値（tensor-core 選択を許可） | 無効になる値（選択を禁止） |
|---|---|---|---|
| CUDA、compute capability major `>= 8` | 許可 | `1`, `true`, 空文字, ` 0`, `false` など先頭が `0` でない任意の文字列 | `0`, `0anything`, `00` など先頭が `0` |
| CUDA、compute capability major `< 8` | 許可判定でも kernel は選ばれない | なし | なし |
| HIP / AMD | この変数を読み取らない | 該当なし | 該当なし |

「許可」は対応 GPU で tensor-core kernel を選択できるという意味です。CUDA の GPU 属性取得が失敗した場合も通常 kernel に fallback します。空文字は unset とは異なりますが、どちらもこのスイッチでは有効扱いです。文字列 `0` は無効ですが `0` に続く文字があっても無効、先頭に空白がある ` 0` は有効です（`engine/src/kernels/cuda/dflash2.cu:1704-1713`）。

## 有効になる条件

- CUDA 版で `df2_attention` が呼ばれる必要があります。通常の engine 経路では DFlash2 drafter がロードされ、その block の attention 処理が実行される場合です（`engine/src/core/dflash2.cpp:539-568`、`engine/src/program/generate.cpp:8195-8203`）。
- CUDA 分岐であることが必要です。HIP/AMD ではこの変数は読まれず、gfx11 WMMA の選択は別の環境変数とデバイス判定に従います（`engine/src/kernels/cuda/dflash2.cu:542-560,1698-1718`）。
- tensor-core kernel のためには GPU の compute capability major が `8` 以上である必要があります。デバイス取得または major 属性取得が失敗するとエラーをクリアして通常 kernel に進みます（`engine/src/kernels/cuda/dflash2.cu:1706-1713`）。
- 値の指定による CLI 引数の上書きや別変数との優先順位はありません。DFlash2 の選択要件（例: `--draft dflash2`、pack、speculative window、draft vocabulary）はこの変数とは独立しています（`engine/src/program/generate.cpp:6477-6503,8195-8203`）。

## 実行時の詳細

`tc_ok` は `df2_attention` 内の関数ローカル `static const bool` です。環境値と CUDA デバイス属性は、プロセスで最初にこの関数が通るとき一度だけ評価され、その結果を後続呼び出しで再利用します。プロセス実行中に環境変数を変更しても再評価されません。最初の呼び出し時のデバイスが判定に使われます（`engine/src/kernels/cuda/dflash2.cu:1696-1715`）。

`tc_ok` が true の場合は `attn_part_tc_kernel`、false の場合は `attn_part_kernel` を起動し、その後どちらも `attn_merge_kernel` を起動します。DFlash2 の drafter は各 layer の block 処理で `df2_attention` を呼びます（`engine/src/kernels/cuda/dflash2.cu:1714-1724`、`engine/src/core/dflash2.cpp:539-568`）。

このスイッチ固有の警告や選択ログはありません。CUDA デバイス属性の取得失敗はログを出さず fallback します。kernel 起動エラー時は共通の `check` が `dflash2 kernel <kernel名>: <CUDA error>` を stderr に出し、同じ内容を含む `std::runtime_error` を投げます（`engine/src/kernels/cuda/dflash2.cu:29-34,1706-1723`）。

## 根拠

- 変数の読み取り、キャッシュ、能力判定、kernel 選択と merge: `engine/src/kernels/cuda/dflash2.cu:1696-1724`
- CUDA kernel 起動エラーのログと例外: `engine/src/kernels/cuda/dflash2.cu:29-34`
- HIP/AMD 側の別判定と変数: `engine/src/kernels/cuda/dflash2.cu:542-560,1698-1702`
- DFlash2 layer block からの attention 呼び出し: `engine/src/core/dflash2.cpp:539-568`
- generate の DFlash2 前提と起動条件: `engine/src/program/generate.cpp:6477-6503,8195-8255`
- 適用 backend の一覧記載: `docs/SETTINGS.md:367`

# `STRATA_OLD_GROUPED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Grouped Expert GPU カーネルの起動時に、改訂前のカーネル群を選択するための A/B 比較用フックです。CUDA 実装と SYCL 実装の両方にあります。通常のGrouped Expert APIの動作を切り替え、単一の処理で選ばれたカーネルを使います。環境変数を読むのはカーネル実装であり、CLI やサーバー設定の解析ではありません。

## 値と判定

値全体の数値変換や真偽値解析は行わず、`getenv()` が返す文字列の先頭1文字だけを比較します。

| 環境変数の状態 | 旧カーネル選択 |
|---|---|
| 未設定 | しない（新カーネルを選ぶ候補） |
| 空文字 | しない |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | する |
| それ以外（例: `0`, `true`, ` 1`, `2`） | しない |

大文字小文字、空白除去、文字列末尾の検査はありません。値が `1` で始まることだけが条件です。CUDA と SYCL の実装で判定は同じです（`src/kernels/cuda/s2_expert_grouped.cu:523-531`、`sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:733-741`）。

## 有効になる条件

この環境変数を読むGrouped Expertカーネル実装がビルドされ、そのAPIが呼ばれた場合に関係します。主な公開関数 `moe_grouped_s2` では、このフラグが新しい grouped kernel 経路を許可するかを決めます（`src/kernels/cuda/s2_expert_grouped.cu:1131-1149`、SYCL版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:1577-1622`）。同じ選択 helper は per-hit の `moe_hit_grouped_s2`、device count版、multi版にも使われます（CUDA版 `src/kernels/cuda/s2_expert_grouped.cu:611-617,715-720,752-757`、SYCL版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:885-890,1047-1052,1112-1117`）。

環境変数が未設定または先頭が `1` 以外でも、常に新カーネルになるわけではありません。新カーネルはactivationとscratchが4バイト境界に揃っている場合だけ使われます。per-hit経路ではさらにexpert blob先頭とblobサイズが8バイト境界に揃い、capacityが `STRATA_GROUPED_PAIR_MIN_HITS` の閾値以上である必要があります。これらを満たさないと旧カーネルへフォールバックします。したがって、この変数は旧カーネルを強制できますが、新カーネルを強制する変数ではありません（CUDA版 `src/kernels/cuda/s2_expert_grouped.cu:550-560`、SYCL版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:760-770`）。

## 実行時の詳細

`old_kernels()` の初回評価時に環境値を読み、関数内 `static const bool` に保存します。`old_kernels()` が最初に実行された後でプロセスの環境を変更しても反映されません。初回評価前に読み取り時期を遅らせる特別な起動処理はなく、最初にGrouped Expert選択判定が必要になった呼び出しで読みます。

実装には環境変数とは別に `moe_grouped_select_old(int)` があり、引数が負なら環境変数の設定へ戻し、0なら旧カーネルを選ばず、0以外なら旧カーネルを選びます。この強制値が設定されている間は環境変数の判定より優先されます。環境値自体はキャッシュ済みなので、負値で戻しても初回に読み込んだ環境値を使います（CUDA版 `src/kernels/cuda/s2_expert_grouped.cu:523-531,596`、SYCL版 `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:733-741,870`）。

カーネル選択はAPI呼び出しごとに行います。従って、選択APIで実行時に強制値を変えると後続の起動に反映しますが、既にキャプチャされたGPU graph内の起動はキャプチャ時に選ばれたカーネルのままです。この選択に関するログ出力は実装箇所にありません。

## 文書との照合

`docs/DETAILS.md` には `STRATA_OLD_GROUPED` の説明を確認できませんでした。ヘッダーコメント `include/strata/kernels/s2_expert_grouped.hpp:113-122` は環境変数による旧カーネル選択と `moe_grouped_select_old` の優先を説明しており、実装と一致します。性能差や実行結果はこの調査では測定していません。

## 根拠

- `src/kernels/cuda/s2_expert_grouped.cu:516-560` — 環境値のキャッシュ、判定、新旧カーネル選択とアラインメント条件。
- `src/kernels/cuda/s2_expert_grouped.cu:596,611-649,715-743,752-790,1131-1180` — 強制選択APIと、この判定を使うGrouped Expert呼び出し経路。
- `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:726-770,870,885-935,1047-1085,1112-1150,1577-1635` — SYCL側の同等実装。
- `include/strata/kernels/s2_expert_grouped.hpp:113-125` — APIコメントと選択仕様。

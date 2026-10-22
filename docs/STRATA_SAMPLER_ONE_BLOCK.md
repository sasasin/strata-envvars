# `STRATA_SAMPLER_ONE_BLOCK`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリ、生成済みコード、テスト専用コードは根拠に含めない。

## 役割

CUDA sampler の非 greedy sampling で、top-k 候補を選ぶ sampled path として one-block kernel を選びます。unset 時の通常経路は split top-k です。one-block kernel は各 token の語彙を1 block で処理し、選択を繰り返して候補を作ってから、共通の top-p / min-p / temperature / draw 処理へ進みます（`src/kernels/cuda/sampler.cu:554-560,1102-1120`）。

## 値と判定

`env_flag()` は `std::getenv()` で値を取得し、未設定、空文字列、文字列全体がちょうど `"0"` の場合だけ false を返します。それ以外の非空文字列は true です。数値変換や大文字小文字変換は行いません（`src/kernels/cuda/sampler.cu:1106-1109`）。

| 環境の状態 | `STRATA_SAMPLER_ONE_BLOCK` の判定 |
|---|---|
| unset | false |
| 空文字列 (`""`) | false |
| `0` | false |
| `1`, `2`, `00`, `false`, ` 0`, `0 ` など | true |

この判定より前に `STRATA_OLD_SAMPLER` が同じ helper で評価されます。こちらが true なら sampled path は旧 `sampler_kernel` となり、`STRATA_SAMPLER_ONE_BLOCK` の値は path 選択に影響しません（`src/kernels/cuda/sampler.cu:1116-1120`）。

## 有効になる条件

- `sample_tokens()` が呼ばれ、`p.greedy == false` かつ `p.temperature > 0` の sampled 分岐に入る必要があります。greedy または温度 0 以下は先に greedy kernel の分岐へ進むため、この変数を使った path 選択をしません（`src/kernels/cuda/sampler.cu:1239-1269`）。
- 上記 sampled 分岐で `STRATA_OLD_SAMPLER` が有効でなければ、この変数が true のとき one-block kernel が選ばれます。false なら split path を選びます。
- split path でも、語彙が merge 上限を超える、行数が `kSplitMaxRows` を超える、stream が capture 中、scratch を確保できない場合は one-block kernel に fallback します。したがって変数 unset でも one-block kernel が使われる入力があります（`src/kernels/cuda/sampler.cu:643-644,1123-1142,1269-1290`）。
- spec verification の `sample_tokens_spec()` は sampled path が split でない場合に `false` を返します。その呼び出し元は通常の `sample_tokens()` に切り替えるため、この変数が有効なら通常 sampler の one-block path に進みます（`src/kernels/cuda/sampler.cu:1347-1369`, `src/core/verify.cpp:3013-3036`）。
- `coupled_draft_sample()` と `spec_draft_sample()` は split kernel を直接起動し、`sampled_path()` を参照しません。この環境変数はこれらの draft sampling kernel の選択を変えません（`src/kernels/cuda/sampler.cu:1324-1342,1372-1390`）。

## 実行時の詳細

path は `sampled_path()` 内の `static const SampledPath` に初回評価時の結果が保存されます。環境変数はプロセス内で初めて sampled path を選ぶ際に評価され、その後にプロセス環境を変更しても再評価されません。初回評価では `STRATA_OLD_SAMPLER` を先に確認し、false の場合にこの変数を確認します（`src/kernels/cuda/sampler.cu:1106-1120`）。

one-block が選ばれると、各 token に対して `sampler_one_block_kernel` を起動します。split が選ばれた場合は、条件が揃えば split part と split merge の2段階で起動し、split 条件を満たさない場合は同じ one-block kernel に進みます（`src/kernels/cuda/sampler.cu:1264-1290`）。この path 選択箇所に環境変数専用のログ出力はありません。kernel launch error の場合は `sample_tokens launch: ...` を stderr に出して終了します（`src/kernels/cuda/sampler.cu:1292-1295`）。

## 根拠

- `src/kernels/cuda/sampler.cu:554-560` — one-block sampled kernel の処理説明。
- `src/kernels/cuda/sampler.cu:1102-1120` — path enum、値判定、`STRATA_OLD_SAMPLER` との優先順位、static cache。
- `src/kernels/cuda/sampler.cu:1239-1298` — greedy / sampled 分岐、split 条件、one-block 起動とログ。
- `src/kernels/cuda/sampler.cu:1347-1369` — spec verification sampler が split path を要求する条件。
- `src/core/verify.cpp:3013-3036` — spec path が使えない場合の通常 sampler への fallback。
- `src/kernels/cuda/sampler.cu:1324-1342,1372-1390` — coupled draft sampler が split kernel を直接使う箇所。
- `CMakeLists.txt:377-385` — `src/kernels/cuda/sampler.cu` が `strata_kernels` に含まれること。

`docs/DETAILS.md` にはこの環境変数についての説明や測定値は見つからなかった。`sycl/src/kernels/cuda/sampler.dp.cpp` には同名変数を使う移植コードがあるが、生成・移植済みコードを根拠から除くという調査範囲に従い、本書ではその実装を現行挙動の根拠にしていない。

# `STRATA_SAMPLER_ONE_BLOCK`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA / SYCL の sampled sampler で、既定の split top-k 経路に代えて、1 token 行ずつ1 blockで処理する `sampler_one_block_kernel` を選びます。greedy sampling の経路はこの選択を参照しません。

## 値と判定

値は `getenv()` で読み、未設定でなく、空文字でなく、文字列全体がちょうど `"0"` でない場合に有効です。数値変換、前後空白の除去、大文字小文字の変換はありません。

| 値 | 判定 |
|---|---|
| 未設定、空文字、`0` | 無効 |
| `1`、`true`、`false`、`00`、`0anything`、空白を含むその他の非空文字列 | 有効 |

ただし、`STRATA_OLD_SAMPLER` も同じ判定で有効なら、そちらが優先されます。その場合 C++ の条件演算子が短絡するため、この変数の値は読み取られません。

## 有効になる条件

- 値の判定と `STRATA_OLD_SAMPLER` の優先順位は CUDA と SYCL で同じです。HIP 側にこの変数を読む実装は見つかりませんでした。
- `sample_tokens()` の sampled 経路で使われます。`p.greedy` が真、または `temperature <= 0` の場合は greedy kernel / GPU 世代に応じた greedy cluster 経路を通り、この変数による切替は行いません。
- 変数が無効なら split 経路が選ばれます。ただし split に必要な scratch を用意できない場合や、語彙ブロック数が上限を超える場合、行数が上限を超える場合、stream / queue が capture 中または状態を取得できない場合は、通常の sampled 呼び出しが one-block 経路へ fallback します。実装上の split 上限は最大64ブロック（各4,096 logits、最大語彙262,144）・64行です。
- speculative verification 用の `sample_tokens_spec()` は split 経路のみを実行します。この変数が有効（または split 条件を満たさない）なら `false` を返し、呼び出し元の verifier は通常の `sample_tokens()` に fallback します。

## 実行時の詳細

CUDA と SYCL の `sampled_path()` は `static const` に選択結果を保存します。最初に sampled 経路で判定した後はプロセス内で再評価されないため、実行中に環境を変更しても反映されません。greedy 呼び出しだけではこの static 値を初期化しません。

有効なら、各 token 行を1 blockで処理し、選択段階の後に既存の sampled tail（top-p / min-p / temperature / draw）へ進みます。無効時は条件が揃えば split の part / merge kernel を使います。失敗理由を示す `STRATA_SAMPLER_ONE_BLOCK` 専用ログはありません。CUDA の kernel launch error は `sample_tokens launch: ...` を stderr に出して終了し、SYCL では例外を catch した場合に例外文字列とファイル・行を stderr に出して終了します。

別の相互作用として、`STRATA_OLD_SAMPLER` が有効なら旧 `sampler_kernel` が選ばれ、本変数は無視されます。speculative verification で split-only の高速経路が使えない場合は、verifier が通常の `sample_tokens()` を呼び出して処理を続けます。

## 文書との照合

`docs/DETAILS.md:1218-1231` は request の sampling 設定や top-k の上限などを説明していますが、この内部 sampler 経路を選ぶ環境変数、その parse 規則、優先順位は記載していません。同ファイルの値や性能記述から本変数の性能効果は判断できないため、ここでは性能値を記載しません。

## 根拠

- 値判定、`STRATA_OLD_SAMPLER` との優先順位、static cache: `src/kernels/cuda/sampler.cu:1102-1120`, `sycl/src/kernels/cuda/sampler.dp.cpp:1289-1303`。
- greedy と sampled 経路の分岐、split / one-block 選択と fallback: `src/kernels/cuda/sampler.cu:1239-1290`, `sycl/src/kernels/cuda/sampler.dp.cpp:1471-1651`。
- split 上限と block の範囲: `src/kernels/cuda/sampler.cu:642-644`, `sycl/src/kernels/cuda/sampler.dp.cpp:969-970`。
- one-block kernel の処理と sampled tail: `src/kernels/cuda/sampler.cu:554-563`。
- speculative verification が split 以外を拒否し、verifier が通常 sampling に fallback: `src/kernels/cuda/sampler.cu:1347-1369`, `src/core/verify.cpp:2313-2337`。
- 文書との照合: `docs/DETAILS.md:1218-1231`。
- テスト専用コード `src/kernels/sampler_parity.cpp:473-479` と `sycl/src/kernels/sampler_parity.cpp:535-541` は選択経路の表示に同名を参照しますが、本番動作の根拠には使用していません。

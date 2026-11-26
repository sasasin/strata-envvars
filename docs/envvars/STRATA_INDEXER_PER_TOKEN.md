# `STRATA_INDEXER_PER_TOKEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の prompt prefill で indexer state を更新する粒度を切り替える内部スイッチです。未設定なら chunk の indexer append を batch API でまとめて行い、設定されていれば chunk 内の各 token に対して単一 append API を順に呼びます。CUDA/HIP 系の prefill と SYCL prefill に読み取り箇所があります。いずれも通常の prompt 経路で選択・attention に進む前に indexer state を更新します（`engine/src/prefill/prefill.cpp:5323-5342`, `engine/src/prefill/prefill.cpp:9428-9443`, `engine/sycl/src/prefill/prefill.cpp:3645-3664`）。

## 値と判定

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP 系 prefill（通常・layer-major）および SYCL prefill | batch append | `getenv` が非 null になる値すべて。例: `1`, `0`, `true`, `false`, `0anything`, 空文字 | なし。値の内容は判定しない |

コードは `std::getenv(...) != nullptr` で有無だけを見ており、文字列比較・数値変換・trim・大文字小文字の判定はありません。したがって `STRATA_INDEXER_PER_TOKEN=0` も token ごとの経路を選び、空文字も設定済みとして扱います（`engine/src/prefill/prefill.cpp:5330-5337`, `engine/src/prefill/prefill.cpp:9431-9438`, `engine/sycl/src/prefill/prefill.cpp:3652-3659`）。

## 有効になる条件

- QSA indexer append を実行する prompt prefill 経路に入ることが必要です。変数名の読み取りは CUDA/HIP 系の通常 prefill と layer-major prefill、および SYCL prefill にあります。QSA indexer append を通らない処理には効果がありません（`engine/src/prefill/prefill.cpp:5323-5342`, `engine/src/prefill/prefill.cpp:9428-9443`, `engine/sycl/src/prefill/prefill.cpp:3645-3664`）。
- 対象の prompt chunk 長は `T` です。設定時は `t = 0..T-1` のループで append し、未設定時は `T` 件を一度に batch append します。`T <= 0` なら設定時の loop は呼び出しません。batch API も `n <= 0` で直ちに戻ります（`engine/src/prefill/prefill.cpp:5332-5341`, `engine/src/prefill/prefill.cpp:9433-9442`, `engine/sycl/src/prefill/prefill.cpp:3654-3663`, `engine/src/kernels/cuda/native_qsa_indexer.cu:341-345`, `engine/sycl/src/kernels/cuda/native_qsa_indexer.dp.cpp:476-480`）。
- CLI 引数や他の環境変数によるこの値の上書きは、対象名の全参照では見つかりません。`terminal/data/settings-register.json` に名前の登録がありますが、これは値の読み取り箇所ではありません。

## 実行時の詳細

それぞれの prefill 関数内で `static const bool` として初回評価時に保存されます。通常 prefill と layer-major prefill は別々の static 変数で、SYCL 側にも独立した static があります。各 static の初期化後に同一プロセス内で環境を変更しても、その経路の選択には反映されません。値を読むのは prompt indexer append に到達した時であり、読み取り時点より前に実行中の環境を変更した場合の反映は、各 static の初期化前かどうかに依存します（`engine/src/prefill/prefill.cpp:5330`, `engine/src/prefill/prefill.cpp:9431`, `engine/sycl/src/prefill/prefill.cpp:3652`）。

未設定時の batch API は chunk の appends をまとめて処理します。設定時は `m.idx_raw` の token ごとの 128 要素領域と対応する device position を使い、同じ chunk を順番に single append します。共通 header は batch append の結果が同じ順序の single append `n` 回と同じ buffer state になると記載し、prompt path では chunk append の後に query が indexer state を読むとしています。そのためこのスイッチが切り替えるのは append の実行粒度であり、selection 用 state の最終内容を切り替える意図ではありません（`engine/include/strata/kernels/native_qsa_indexer.hpp:34-39`, `engine/src/prefill/prefill.cpp:5323-5341`, `engine/sycl/src/prefill/prefill.cpp:3645-3663`）。

## ログと測定値

正常にどちらの経路を選んだかを示す専用ログはありません。append 中に `std::exception` が発生すると、呼び出し側は `prefill indexer: ` を付けて `err` に格納し、その prefill 関数から `false` を返します（SYCL も同じ接頭辞です）。この環境変数による速度差の測定値は、調査対象ソースおよび `docs/DETAILS.md` で確認できません（`engine/src/prefill/prefill.cpp:5342`, `engine/src/prefill/prefill.cpp:9443`, `engine/sycl/src/prefill/prefill.cpp:3664`）。

## 根拠

- `engine/src/prefill/prefill.cpp:5323-5342` — 通常 prefill の batch / token 単位分岐とエラー処理。
- `engine/src/prefill/prefill.cpp:9428-9443` — layer-major prefill の同じ分岐とエラー処理。
- `engine/sycl/src/prefill/prefill.cpp:3645-3664` — SYCL prefill の同じ分岐とエラー処理。
- `engine/include/strata/kernels/native_qsa_indexer.hpp:34-39` — batch append の位置範囲と single append 順次実行時と同じ buffer state という API 契約。
- `engine/src/kernels/cuda/native_qsa_indexer.cu:341-380`、`engine/sycl/src/kernels/cuda/native_qsa_indexer.dp.cpp:476-525` — backend ごとの batch API 実装。

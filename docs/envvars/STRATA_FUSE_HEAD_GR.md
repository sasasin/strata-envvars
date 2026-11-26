# `STRATA_FUSE_HEAD_GR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

最終層の GR 書き込み（MoE 出力 `y` と注入値 `inj2` を residual `R` に反映する処理）と、最終 head 用 hyper-connection mixer の読み出しを `fused_gr_read_multi` にまとめる開発・実験用スイッチ。通常は最終層で `gr_write` / `gr_write_multi` を行ってから head mixer を読むが、この値が有効な経路ではその書き込みを省き、head mixer の fused read に `bo_prev` と `inj_prev` を渡して同じ段階で適用する。CUDA/HIP 共用 engine の MTP decode と batch MTP、および CUDA/HIP 共用・SYCL の verify decode に読み取りがある。これ自体は router、expert 選択、head 行列演算を切り替える設定ではない。`engine/src/core/mtp.cpp:1462-1519, 2592-2653`、`engine/src/core/verify.cpp:2984-2989, 3037-3071`。

## 値と判定

判定方法は MTP と verify で異なる。いずれも文字列全体の厳密比較や範囲検査ではない。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP 共用 MTP（通常・batch）、SYCL MTP | `false` | `std::atoi(v) != 0`。先頭の空白と符号付き整数を `atoi` が解釈し、変換結果が 0 以外なら有効。例: `1`, `-1`, `2tail`, ` 1` | `atoi` の結果が 0。例: 空文字、`0`, `0tail`, `true`, 数字で始まらない文字列 |
| CUDA/HIP 共用 verify、SYCL verify | `false` | `e[0] == '1'`。文字列の先頭 1 文字だけを見る。例: `1`, `10`, `1anything` | 空文字または先頭が `1` 以外。例: `0`, `true`, ` 1`, `2` |

MTP の `atoi` 判定は変換可能な数字の後ろを検査しない。verify は整数変換をしないため、`1tail` は有効だが `+1` や先頭空白付きの ` 1` は無効である。負値の例 `-1` は MTP では有効、verify では無効。各判定は `engine/src/core/mtp.cpp:1385-1388, 2532-2535`、`engine/sycl/src/core/mtp.cpp:1090-1093`、`engine/src/core/verify.cpp:2780-2783`、`engine/sycl/src/core/verify.cpp:1698-1701`。

## 有効になる条件

- MTP では、該当する MTP decode / batch MTP の処理が実行され、MTP の関数内 static 判定が true であること。コード上、この経路には verify のような head loaded・layer split・control vector の追加条件は置かれていない。MTP が最終 mixer を計算して head に渡す処理は `engine/src/core/mtp.cpp:1479-1519, 2615-2653` と `engine/sycl/src/core/mtp.cpp:1193-1225`。
- verify では、環境値が有効で、処理範囲が最終層まで届く（`le_ == g.n_layers`）、native head がロード済み、かつ control vector が最終層を覆っていないことが必要。条件不足なら `fuse_head_gr` は false となり、最終層の GR 書き込みは通常経路で実行される。CUDA/HIP 共用と SYCL で条件は同じ。`engine/src/core/verify.cpp:2780-2785, 2984-2989`、`engine/sycl/src/core/verify.cpp:1697-1704, 1839-1847`。
- verify の最終 mixer では `mix_q8` が true の場合、`fuse_head_gr` が true でも Q8 mixer 分岐が先に選ばれ、環境変数による GR fused-read 分岐は実行されない。`mix_q8` は head loaded に加えて `output_hc_down` と `output_hc_up` の両方に `hc_q8` がある場合に true。`engine/src/core/verify.cpp:3030-3051`、SYCL は `engine/sycl/src/core/verify.cpp:1873-1893`。
- 最終 head が使用されない layer-split の前段では verify が head 処理前に handoff を返すため、この head 用 fused 処理には到達しない。`engine/src/core/verify.cpp:3003-3014`、`engine/sycl/src/core/verify.cpp:1862-1868`。
- MTP で `STRATA_NO_MULTI_GR` が有効でも、`fuse_head_gr` が true の場合は通常の GR 書き込み分岐を抑止し、fused read 側に進む。head mixer が別方式になる条件として、CUDA/HIP 共用 MTP は `STRATA_HEAD_MIX_MULTI` を `mtp_head_mix_multi_on()` で判定するが、`fuse_head_gr` が true ならその multi-read 分岐より優先される。`engine/src/core/mtp.cpp:1458-1513, 2592-2648`、`engine/sycl/src/core/mtp.cpp:1173-1225`。

## 実行時の詳細

各読み取りは関数内 `static const bool` の初期化ラムダで行われる。したがって各読み取り箇所では最初にその関数が到達した時の環境値をキャッシュし、同じプロセスで後から環境を変更しても再評価されない。MTP の通常・batch 経路と verify 経路は別々の static である。MTP の CUDA/HIP 共用実装には同じ名前の読み取りが2箇所あり、SYCL 実装には MTP と verify 各1箇所、CUDA/HIP 共用 verify に1箇所ある。`engine/src/core/mtp.cpp:1385-1388, 2532-2535`、`engine/sycl/src/core/mtp.cpp:1090-1093`、`engine/src/core/verify.cpp:2780-2785`、`engine/sycl/src/core/verify.cpp:1698-1703`。

有効時、MTP は MoE 結合後の `y` と `inj2` を最終 mixer に渡し、最終 GR 書き込みと mixer 読み出しを一つの `fused_gr_read_multi` 呼び出しで行う。その結果 `sample_` を量子化して head（通常または draft head）の logits を計算し、後続の argmax / greedy sampling を行う。無効時は GR 書き込み後に multi-read（条件が合わなければ行ごとの `gr_read`）を行う。`engine/src/core/mtp.cpp:1462-1519, 2592-2664`、`engine/sycl/src/core/mtp.cpp:1173-1225`。

有効な verify では各 group の最終層で通常 `gr_write` をスキップし、最終 head の mixer 経路で `bo_`、`inj2_` と residual を `fused_gr_read_multi` に渡す。Q8 mixer 分岐が選択される場合はそちらが先に処理される。verify の `T` 行 head 処理や logits / argmax の後続処理自体を省略するスイッチではない。`engine/src/core/verify.cpp:2984-2989, 3016-3072`、`engine/sycl/src/core/verify.cpp:1839-1847, 1873-1910`。

## ログと測定値

CUDA/HIP 共用 verify は head mixer の処理時に `head: final mixer q8=%ld fuse_head_gr=%ld native_head=%ld` を `strata::dispatch::notef` で記録する。ここで `fuse_head_gr` は環境値だけでなく verify の追加条件を反映した実効値であり、`mix_q8=1` の場合にも 1 と表示され得る（その場合 mixer 分岐は Q8 が優先される）。MTP と SYCL verify のこの変数専用ログは見つからなかった。ソース・関連 docs に本変数の測定値は見つからなかったため記載しない。`engine/src/core/verify.cpp:3030-3036`。

## 根拠

- CUDA/HIP 共用 MTP の値読み取りと最終 mixer/head: `engine/src/core/mtp.cpp:1385-1388, 1462-1519, 2532-2535, 2592-2664`
- SYCL MTP の値読み取りと最終 mixer: `engine/sycl/src/core/mtp.cpp:1090-1093, 1173-1225`
- CUDA/HIP 共用 verify の読み取り、適用条件、最終層・head 経路、ログ: `engine/src/core/verify.cpp:2780-2785, 2984-2989, 3016-3072`
- SYCL verify の読み取り、適用条件、最終層・head 経路: `engine/sycl/src/core/verify.cpp:1697-1704, 1839-1847, 1873-1910`

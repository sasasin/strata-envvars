# `STRATA_SYCL_F16_EXPERT_PAIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の MoE prefill で、条件を満たす native expert を 2 件ずつ専用の FP16 XMX gate/up・down カーネルにまとめて処理する実験的な切替。未設定時はこの専用経路を選ばない。変数が有効でも、対象のレイアウト・expert 形状でない場合や MMQ / XMX mode 1・2 の場合は通常の処理経路を使う（`sycl/src/prefill/prefill.cpp:4309-4311, 4686-4720`）。

この名前を環境から読む実装は `sycl/src/prefill/prefill.cpp` の 1 箇所だけ。`data/settings-register.json:39885-39895` は候補一覧用レジストリであり、実行時の読み取りではない。

## 値と判定

| ビルド / 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL prefill の非 fused MoE 経路 | `false` | 値の先頭文字が ASCII `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1`, `x1` |

実装は `getenv` が null でないことに加えて `v[0] == '1'` だけを見る。文字列全体の比較や数値変換はなく、大文字小文字・空白除去・後続文字の検証もない。空文字は設定済みでも無効。読み取り結果は関数内 `static const bool` に保存されるため、最初にこのコードへ到達した後の環境変更は反映されない（`sycl/src/prefill/prefill.cpp:4309-4310`）。

## 有効になる条件

- SYCL backend の `prefill.cpp` で MoE を通常処理する経路に入る必要がある。fused MoE 経路に入った場合、この判定と専用経路へ進まない（`sycl/src/prefill/prefill.cpp:3705-3735, 4309`）。
- `lay.native` が true、`use_mmq` が false、`strata::prefill::xmx::mode() == 0` であること（`sycl/src/prefill/prefill.cpp:4310`）。`STRATA_PF_XMX` は `mode()` 内でも初回に static cache され、Alchemist では未設定時 mode 2、他の世代では未設定時 mode 0。`STRATA_PF_XMX=0` は mode 0 を選ぶ。AOT build macro と GPU 世代が要求 mode を無効化して mode 0 に戻す経路もある（`sycl/src/prefill/xmx_moe.dp.cpp:149-173`）。
- 現在の層の gate/up type ID が `16` または `22`、down type ID が `42`、`n_ff == 640`、`n_embd == 2560`、その expert の routed row 数 `ne` が `1..16` であること（`sycl/src/prefill/prefill.cpp:4686-4690`）。条件外の expert はこの専用ペア経路を使わず、後続の通常 dequantize / GEMM 経路へ進む（`sycl/src/prefill/prefill.cpp:4700-4720`）。
- CLI 引数や別設定による値の上書きはこの読み取り箇所にはない。MMQ の選択は `use_mmq` を通じて専用経路を無効にし、`STRATA_PF_XMX` は XMX mode 判定を通じて相互作用する（`sycl/src/prefill/prefill.cpp:3690-3692, 4310`）。

## 実行時の詳細

判定が真で対象 expert に一致すると、Strata は gate/up を FP16 に dequantize し、入力行・重み・出力バッファと down 重みを pending slot に登録する。2 件そろうと `f16_expert_pair::gu` と `f16_expert_pair::down` を呼び、専用カーネルが gate/up と SwiGLU、続いて down projection を計算する（`sycl/src/prefill/prefill.cpp:4314-4321, 4686-4698`; `sycl/include/strata/prefill/f16_expert_pair.hpp:31-73, 75-94`）。

pending が 1 件だけで flush された場合は専用ペア kernel を使わず、down を plain FP16 に dequantize して通常の FP16 GEMM と SwiGLU、down GEMM を実行する（`sycl/src/prefill/prefill.cpp:4321-4329`）。staging slot は最後の down 読み取り後に同期して解放され、処理末尾にも残りを flush する（`sycl/src/prefill/prefill.cpp:4330-4336, 4853-4854`）。

対象条件にある `ne <= 16` などを満たさない場合も専用ペア経路を迂回する。対象条件に適合する expert が続かない場合、pending 1 件の flush 先は上記の通常 FP16 経路である（`sycl/src/prefill/prefill.cpp:4686-4720`）。環境値はプロセス内で初回到達時に一度だけ読み取られ、後の prefill/chunk でも cache 値を使う（`sycl/src/prefill/prefill.cpp:4309`）。

## ログと測定値

この変数の有効・無効を知らせる専用ログはない。通常の対象外条件も、この変数についての警告やエラーを出す実装は見当たらない。SYCL 例外が staging 中に発生した場合は `exc.what()` とファイル・行を stderr に出して `exit(1)` する一般的な経路があるが、変数固有の診断ではない（`sycl/src/prefill/prefill.cpp:4391-4397`）。この変数に結び付く条件付き測定値はソース・`docs/DETAILS.md` に確認できなかった。

## 根拠

- 候補名の実行時読み取り、cache と有効条件: `sycl/src/prefill/prefill.cpp:4309-4311`
- ペア経路の適用条件と fallback: `sycl/src/prefill/prefill.cpp:4686-4720`
- ペア kernel の計算内容: `sycl/include/strata/prefill/f16_expert_pair.hpp:31-73, 75-94`
- flush、slot 同期、末尾処理: `sycl/src/prefill/prefill.cpp:4314-4336, 4853-4854`
- XMX mode の環境値・cache・build / GPU 条件: `sycl/src/prefill/xmx_moe.dp.cpp:149-173`
- 一般的な SYCL 例外終了経路: `sycl/src/prefill/prefill.cpp:4391-4397`

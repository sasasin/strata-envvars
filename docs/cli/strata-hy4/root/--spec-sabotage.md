# `strata-hy4 --spec-sabotage`（CUDA/HIP）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--spec-sabotage` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

投機デコードの検証・ベンチマーク向けに、draft を意図的にランダムな token ID に置き換え、受理率が低い状況を作ります。SpecCfg の初期値は無効で、このフラグを指定すると有効になります。コメントでも test only とされています。単独で投機デコードを有効にするフラグではありません。通常のオフライン生成では `--draft dfly2` と正の `--gen` が必要です。サーバーでは drafter が利用可能な場合に SpecCfg が使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:425, 701`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`、`engine/src/hy4flash/run/hy4_spec.hip.h:18-30`）。

## 使い方

```sh
# DFly2 を明示して生成し、投機デコードの低受理率ケースを試す（空の出力ディレクトリを指定）
strata-hy4 --model model.strata --tokens prompt.ids --draft dfly2 --gen 64 --spec-sabotage --out new-empty-output-dir

# サーバーモードでも SpecCfg にフラグを渡す（モデルに drafter があり、初期化できる場合に適用）
strata-hy4 --model model.strata --serve --spec-sabotage
```

## 値と既定値

値を取りません。既定値は無効（`SpecCfg::sabotage = false`）で、指定時は `true` に設定されます。parser はこの引数に `nxt()` を呼ばないため、後続の引数を値として消費しません。繰り返し指定しても同じ真偽値を設定するだけです。数値・範囲・空値の validation はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384, 425`、`engine/src/hy4flash/run/hy4_spec.hip.h:18-30`）。

## 実行時の動作

Spec の各反復で、まず通常の drafter 呼び出しを行います。その後このフラグが有効なら、anchor 以降の draft 列を長さ `Kd` の線形列に作り替え、各 draft の confidence を `0.9`、reach を `0.9^j` にします。token ID はプロセス内 static 状態の xorshift 列から `xs % 100000` で生成されます。その列を使って既存の `choose_m` と target 側の検証へ進みます。したがって drafter の計算自体はスキップしません（`engine/src/hy4flash/run/hy4_spec.hip.h:269-287, 310-338`）。

Sabotage 中は adaptive の early-exit 閾値を 0 にし、draft tree 生成にも `false` を渡すため tree 分岐を使わず、置換後の線形 draft を検証します（`engine/src/hy4flash/run/hy4_spec.hip.h:284-310, 316-332`）。これは「最悪ケース」用というコードコメントの意図を持ちますが、実際の受理数・速度は入力や実行条件で変わり、固定値ではありません。

この設定は parser から `ServeOpts::spec` にコピーされ、サーバー側で drafter が初期化でき、`r.Tc >= 8` の場合に生成した `Spec` に渡されます。オフライン経路では `draft == "dfly2" && gen > 0 && !alloc_only` のとき Spec が実行されます。従って `--spec-sabotage` だけでは投機経路にならず、drafter を使えない場合も効果はありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-570, 701`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`）。

相互作用として `--spec-nodraft` も `sabotage = true` を設定し、さらに `nodraft = true` として drafter 呼び出し自体を飛ばす別動作を選びます。また `--ab-sab` は A/B 測定の通常 spec 実行後に設定を複製して `sabotage = true` にし、ランダム draft の比較測定を追加します（`engine/src/hy4flash/run/hy4_main.hip.cpp:425-428, 914-989`、`engine/src/hy4flash/run/hy4_spec.hip.h:287-314`）。

## 適用条件と副作用

- CUDA/HIP の `strata-hy4` root parser の設定です。Metal 版にも同名フラグがありますが、別コマンドスコープであり、この文書の対象外です（`engine/src/hy4flash/run/hy4_main.hip.cpp:425`、Metal parser は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1556-1565`）。
- Sabotage 用 token ID は `100000` を法として生成されます。ここで確認したコード範囲には、生成した ID を model vocabulary の範囲内に制限する処理はありません。全 model で安全に使える範囲は確認できませんでした。
- 有効時の目的は検証用に draft 列を改変することです。Spec の出力・計測に影響し、通常の生成品質を比較する設定ではありません。
- 通常の offline spec 生成経路では、生成 token ID を標準出力に出し、decode 統計を標準エラーに出力してから `<out>/gen_ids.txt` に書きます。`--margins` も指定した場合は margins と hashes のファイルも書きます。これは spec 経路全体の副作用であり、フラグ専用の出力ではありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:992-1017`）。

## 出力とエラー

このフラグ自体に専用のメッセージや validation error はありません。認識されない引数は `unknown arg ...` を標準エラーに出して終了コード 2 になります。Spec 実行中のエラーは `spec: ...` を標準エラーに出して終了コード 1 になります。サーバーの Spec 利用可否は drafter 初期化などに依存し、利用不能時はサーバー側で drafter なしに続行する経路があります（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505, 1002-1005`、`engine/src/hy4flash/run/hy4_serve.hip.h:320-341`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-384, 408-428` — `draft` の既定値、値なし parser、SpecCfg の設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-570, 701, 992-1017` — server への設定転送、offline spec 条件、出力・ファイル書き込み。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-30, 269-338` — sabotage 設定、draft 置換、early-exit/tree 条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:914-989` — A/B 測定と `--ab-sab` の相互作用。
- `engine/src/hy4flash/run/hy4_serve.hip.h:320-341` — server 側の drafter 条件と Spec 構築。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1556-1565` — 同名 option の Metal parser。別 scope のため本文の挙動根拠には使用していません。

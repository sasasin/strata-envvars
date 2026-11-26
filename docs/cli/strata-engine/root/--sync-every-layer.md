# `--sync-every-layer`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--sync-every-layer` |
| 別名 | なし |
| 値 | 取らないフラグ。既定値は無効（`false`） |

## 役割

`--no-capture` で各層を直接実行するとき、各層の処理後に GPU ストリームを同期し、非同期エラーをその層の位置で検出するデバッグ用オプションです。GPU エラーが後続層やトークン末尾で初めて表面化する状況を、原因となった層に結び付けるために使います。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-capture --no-pool --sync-every-layer
```

`--tokens` は必須です。`--no-capture` を指定すると CPU expert pool を使えないため、エンジンは `--no-pool` も要求します。上の例はその GPU-only 経路を明示しています（`engine/src/program/generate.cpp:1210-1214,10557-10571`）。

## 値と既定値

値は取りません。parser は `Options::sync_every_layer` を `false` で初期化し、オプションを見つけると `true` にします。同じフラグを複数回指定しても値を重ねて変更する処理はありません（`engine/src/program/generate.cpp:847,3932`）。

有効範囲などの値検証はありません。未知の引数は stderr に `unknown argument: ...` と usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4273`）。

## 実行時の動作

parser が設定した値は、`o.no_capture` が真のときに呼ばれる `session_token` に渡されます。通常の捕捉経路では `session_run_token` または `session_loop` が呼ばれ、この値は渡されないため、`--sync-every-layer` 単独では層ごとの同期は行われません（`engine/src/program/generate.cpp:24296-24314`）。

`session_token` は各層の `block_layer` が成功した後、フラグが有効ならその層ごとに CUDA ストリームを同期します。同期の失敗時は `layer N: <CUDA error>` を設定して処理を中断し、呼び出し元が `strata generate: session_token: ...` を stderr に出して終了コード 1 を返します（`engine/src/core/session.cpp:801-842`; `engine/src/program/generate.cpp:24296-24301`）。この同期により、後続処理まで遅れて現れ得る非同期 GPU エラーを、検出した層の番号とともに報告します。

## 適用条件と副作用

- 層ごとの同期が行われるのは `--no-capture` 経路だけです。捕捉経路でも parser はフラグを受理しますが、値は実行関数に渡されません（`engine/src/program/generate.cpp:24296-24314`）。
- `--no-capture` と `--no-pool` の組み合わせが必要です。`--no-capture` だけを指定すると、CPU expert pool がない経路で routed experts が実行されないため、エンジンは GPU-only 実行を意図した場合に `--no-pool` を併記するよう stderr に説明して終了コード 2 を返します（`engine/src/program/generate.cpp:10557-10571`）。
- 同期は層ごとに実際のストリーム待ちを発生させます。通常の高速経路では行わない同期であり、デバッグ用の動作です（`engine/src/core/session.cpp:830-839`）。

## 出力とエラー

正常時にこのフラグ固有の出力はありません。`block_layer` 自体の失敗は層番号を付けて `session_token` から返され、呼び出し元が stderr に出力して終了コード 1 を返します（`engine/src/core/session.cpp:818-827`; `engine/src/program/generate.cpp:24296-24301`）。層後の同期エラーも同様に終了コード 1 となり、同期した層と CUDA エラー文字列が報告されます（`engine/src/core/session.cpp:830-839`; `engine/src/program/generate.cpp:24296-24301`）。

## 根拠

- parser の既定値とフラグ処理: `engine/src/program/generate.cpp:847,3932`
- `strata generate` の usage と引数構文: `engine/src/program/generate.cpp:1208-1214`
- 直接実行経路への値の受け渡し、および捕捉経路: `engine/src/program/generate.cpp:24296-24314`
- `--no-capture` に `--no-pool` を要求する検査と失敗出力: `engine/src/program/generate.cpp:10557-10571`
- 1層ごとの `cudaStreamSynchronize` と失敗時の層番号・エラー文字列: `engine/src/core/session.cpp:801-842`
- ツール ID、parser 所在、文書 scope: `docs/cli/000_cli_tools.md:7-10`; 索引リンクと `strata-engine` の root scope: `docs/cli/README.md:1036-1042,1214-1219`

# `--stop-eos`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象リポジトリの調査開始時の状態は `main...origin/main` で、未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--stop-eos` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

通常のトークン生成で、生成トークンが end-of-turn token に一致したとき生成を終了します。既定では無効です。対象は CMake で生成されるネイティブ engine CLI であり、Terminal CLI の同名実行ファイルとは別の parser です（索引のスコープ: [`docs/cli/README.md`](../../README.md)、`strata-engine` の説明）。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --max-new 64 --stop-eos
```

`--tokens` の値は実際に使うモデルに対応した token ID 列に置き換えてください。engine の usage は `strata generate --pack DIR --tokens "1,2,3" [options]` を示しています。

## 値と既定値

- `--stop-eos` は値を取らず、指定すると `stop_eos = true` になります。未指定時は `false` です（`src/program/generate.cpp:706-708, 2631`）。
- このフラグ自体に数値などの validation はありません。値を続けて渡すと、その値は別引数として処理され、未知の引数として usage を表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。
- 既定の EOS ID は `248044` と `248046` です（`src/program/generate.cpp:706-708`）。`--eos-ids LIST` を指定すると既定リストを置き換え、値の解析成功時に `stop_eos` も有効化します。そのリストはカンマまたは空白区切りの非負整数で、空リスト・不正値は拒否されます（`src/program/generate.cpp:1097-1115, 2735-2739`）。

## 実行時の動作

通常の生成ループでは、プロンプト終端以降にサンプラーが生成した ID を `produced` に追加した後、その ID が有効な EOS ID のいずれかならループを終了します。したがって EOS ID 自体も出力に含まれます。終了後は `output` 行に生成済み token ID が出力されます（`src/program/generate.cpp:16080-16083, 16867-16872`）。

投機生成ループも、採用した出力 token を `produced` に追加して EOS ID を確認し、一致した時点でそのラウンドを終えます（`src/program/generate.cpp:16680-16692`）。通常生成と投機生成のどちらでも `--max-new` に達した場合は EOS 判定による停止を待たずに上限で終了します（`src/program/generate.cpp:16080-16083, 16681-16692`）。

`--serve` で token 入力を省略する経路では、engine がリクエスト用の初期 token を設定し、`stop_eos` を true にします（`src/program/generate.cpp:3168-3173`）。ただし serve の専用ループには EOS ID を直接判定してリクエストを終了する処理もあり、batch 経路では終了理由 `stop` を付けます（`src/program/generate.cpp:11640-11653, 11822-11838`）。そのため `--stop-eos` を serve 全経路の EOS 認識を切り替えるフラグとは解釈できません。

## 適用条件と副作用

- 通常の単発生成では、フラグを指定しなければ EOS ID を生成しても、このフラグによる終了判定は行いません。指定時は一致した最初の生成 EOS token を含めて生成を止めます（`src/program/generate.cpp:16080-16083`）。
- `--eos-ids` は EOS 集合を置き換えると同時に停止を有効化するため、既定 ID も停止対象に残したい場合は新しいリストにも含める必要があります（`src/program/generate.cpp:708, 2735-2739`）。
- ソース上、このフラグによるファイル・ネットワーク・子プロセスへの副作用は確認できません。主な効果は生成ループの早期終了です。

## 出力とエラー

- EOS で終了した場合、EOS token は通常の生成出力に含まれ、終了後の `output` 行にも表示されます（`src/program/generate.cpp:16080-16083, 16867-16872`）。
- `--stop-eos` 単独に対する値の validation error はありません。余分な値や未知の引数は `unknown argument: ...` を stderr に出し、usage を stderr に表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。
- `--eos-ids` の不正な値はエラー内容を stderr に出して終了コード 2 になります（`src/program/generate.cpp:2735-2738`）。

## 根拠

- parser の既定値とオプション分岐: `src/program/generate.cpp:706-708, 2631`。
- EOS ID リストの形式・検証・停止有効化: `src/program/generate.cpp:1097-1115, 2735-2739`。
- 通常生成および投機生成での停止判定: `src/program/generate.cpp:16080-16083, 16100-16102, 16680-16692`。
- serve の既定有効化と専用ループでの終端処理: `src/program/generate.cpp:3168-3173, 11640-11653, 11822-11838`。
- 出力・未知引数エラー: `src/program/generate.cpp:2787-2792, 16867-16872`。

同一 revision の既存 CLI `--help` は実行せず、ソース parser と実使用箇所を根拠にしています。ビルド済み実行ファイルおよび Release 配布物の挙動はこの調査では確認していません。

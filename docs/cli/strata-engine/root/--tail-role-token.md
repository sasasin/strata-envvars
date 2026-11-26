# `--tail-role-token`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数。`--serve` 用） |
| オプション | `--tail-role-token` |
| 別名 | なし |
| 値 | 整数として扱う token ID |

## 役割

`--serve` の会話 prompt cache で、最後の assistant turn の直前に特定 role の turn がある場合、checkpoint の境界をその turn の開始位置まで戻します。末尾に付加される reasoning-effort 用 system turn を会話履歴の checkpoint から外し、次のリクエストで reasoning effort が変わっても共有できる会話部分を再利用するための opt-in 設定です。prompt 自体から turn を削除する設定ではありません。

## 使い方

```sh
# serve の会話 prompt cache で、system role token ID 8678 の末尾 turn を checkpoint から除外する
strata --serve --model /path/to/model.gguf --prompt-cache 8 --tail-role-token 8678
```

`8678` は例です。実際には対象モデルの tokenizer が返す role token ID を指定します。Strata の server は reasoning effort を末尾の system turn に置く構成でこの引数を渡します。

## 値と既定値

- 値は `std::atoll` で `int64_t` に変換されます。parser はこの値について明示的な範囲検査や値形式の検証を行いません。
- 省略時の既定値は `-1` です。`tail_role_token >= 0` のときだけ checkpoint 境界の調整を行うため、負数は無効値として扱われます。
- 同じ引数を複数回指定した場合、parser は順に代入するため最後の値が残ります。
- 値を省略すると `--tail-role-token needs a value` を stderr に出して終了コード 2 で終了します。

## 実行時の動作

エンジンはまず `--prompt-cache > 0` かつ `--turn-token >= 0` の場合に、再開位置より後ろから最後の `turn_token` を探します。これが見つかり、かつ `tail_role_token >= 0` なら、その直前にある turn 開始 token を一つ探します。直前 turn の開始 token の次の token が `tail_role_token` と一致したときだけ、checkpoint 境界をその直前 turn の開始位置へ移します。一致しない場合、または必要な turn 境界がない場合は通常の最後の turn 境界を使います。したがって値は `--turn-token` とともに解釈され、prompt cache が無効なときや turn token を無効化したときには効果がありません。

この引数は checkpoint の位置にだけ作用します。指定 token を含む turn は生成用 prompt に残ります。`--turn-token`、`--prompt-cache` と合わせて使い、正しい tokenizer の role token ID を指定してください。

## 適用条件と副作用

- help と parser の説明はいずれも `--serve` 用として記載されています。通常の単発生成での作用はソース上で確認できません。
- CUDA/HIP 系の共通 parser と SYCL parser の双方に登録され、いずれも既定値 `-1`、`std::atoll` による変換、同じ checkpoint 境界条件を使います。
- checkpoint 境界を変えるだけで、ファイル・ネットワーク・プロセスを直接操作する副作用はありません。
- Qwen3.6 family は別 parser に振り分けられるため、本書は `strata-engine/root` の共通 parser の説明です。Qwen3.6 の別 scope にこの引数があるかは本調査では扱いません。

## 出力とエラー

正常な値に対する専用の標準出力・標準エラー出力はありません。値形式を検証する専用エラーもありません。値を欠落させた場合のエラーと終了コードは「値と既定値」に記載したとおりです。未知の引数は `unknown argument: ...` を stderr に出し、usage を表示して終了コード 2 になります。

## 根拠

- `engine/src/program/generate.cpp:1131-1138` — `--turn-token` と `tail_role_token` の既定値・意図。
- `engine/src/program/generate.cpp:1335-1337` — help の値名、`--serve` scope、既定値と説明。
- `engine/src/program/generate.cpp:3842-3847` — 引数値取得と値欠落時の stderr・終了コード。
- `engine/src/program/generate.cpp:4115-4117` — parser 登録と `std::atoll` 変換。
- `engine/src/program/generate.cpp:11600-11612` — prompt cache 条件、末尾 turn の検索、role token 一致時の checkpoint 境界変更。
- `engine/src/program/generate.cpp:4268-4273` — 未知引数の失敗経路。
- `engine/sycl/src/program/generate.cpp:748-755`, `912-914`, `2093-2095`, `11600-11612` — SYCL parser の既定値・help・登録・境界判定が共通 parser と同じであること。
- `docs/cli/README.md:1036-1041`, `1217-1220` — `strata-engine` のツール ID / root scope と索引上のリンク。索引は依頼により変更していません。

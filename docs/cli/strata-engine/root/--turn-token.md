# `--turn-token`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（トップレベル、`--serve` 用） |
| オプション | `--turn-token ID` |
| 別名 | なし |
| 値 | token ID を表す符号付き整数。既定値 `248045` |

## 役割

`--serve` の会話 prompt において、チャットの各 turn を開く token ID を指定します。prompt cache が有効な場合、この token の位置を turn 境界として使い、次のリクエストで再利用する会話 prefix の checkpoint 位置を決めます。生成停止用の EOS token を指定するオプションではありません。

## 使い方

```sh
strata --serve --pack /path/to/model.gguf --turn-token 248045
```

モデル指定や server 入力の詳細は環境に合わせて追加してください。`248045` は parser の既定値でもある `<|im_start|>` の token ID です（`src/program/generate.cpp:754-756, 928`）。

## 値と既定値

- 値を省略すると parser は stderr に `--turn-token needs a value` を出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。
- 値は `std::atoll` で変換され、変換エラーや範囲を検査する専用 validation はありません（`src/program/generate.cpp:2667`）。したがって、数値として解釈できない文字列は `0` になり、数値の後ろにある非数値部分も厳密には拒否されません。値は token ID と一致するよう指定してください。
- 負数も parser では拒否されませんが、実行時の境界探索条件 `turn_token >= 0` を満たさないため、turn token による checkpoint 境界検出は無効になります（`src/program/generate.cpp:13980-13983, 14001-14005`）。
- 同じオプションを複数回指定した場合は、parser が読むたびに同じ field を代入するため最後の値が残ります（`src/program/generate.cpp:2416-2420, 2667`）。
- token ID がモデルの語彙範囲内かはこのオプションの parser では検証されません。実行時は prompt の token ID と整数値の完全一致を探します（`src/program/generate.cpp:13980-13983`）。

## 実行時の動作

この値の実利用箇所は `--serve` の request prompt 処理です。`--prompt-cache` が `0` 以下、または turn token が負数なら通常の turn 境界を探しません。条件を満たす場合、再開位置 `resume` より後から prompt の末尾側へ逆順に走査し、最後に現れる一致 token の index を `turn_at` とします（`src/program/generate.cpp:13975-13983`）。この位置を prefill の分割点に加え、その index の prefix を処理したところで checkpoint を保存します。したがって、境界 token 自身以降はこの checkpoint の prefix に含めず、次の request で変わり得る assistant header などを読み直せます（`src/program/generate.cpp:14037-14042, 14065-14085, 14123-14127`）。

関連する設定との関係は次のとおりです。

- `--prompt-cache N` が正であることが turn checkpoint の前提です。既定の checkpoint 数は `6` です（`src/program/generate.cpp:725-728, 13980-13983`）。
- `--prompt-cache-root N` が正で、prompt を token 0 から読む場合（またはそこから再開した場合）は、最後の turn より前にある最初の一致 token も root checkpoint 候補として調べます。位置 `i` が `N` 以上の場合に選ばれます。既定値は `2048` です（`src/program/generate.cpp:751-756, 13993-14005`）。
- `--tail-role-token ID` が有効（0 以上）で、最後の turn marker の直前にある前の turn marker の次 token が指定 role token と一致すると、checkpoint 境界をその前の marker に移します。これは末尾の短い effort turn を会話 checkpoint から除くための別設定です（`src/program/generate.cpp:757-761, 13984-13992`）。
- 環境変数 `STRATA_CACHE_MESSAGE_BOUNDARY` が非ゼロの場合、単一 GPU では既存の turn boundary より前に追加 checkpoint を選ぶことがあります。selector は prefix が 8,192 token 以上で、末尾側の長さが 1,024 token 以下の場合に限り候補を返します。layer split (`multi_gpu`) では使われません（`src/program/generate.cpp:14007-14013`; `include/strata/program/message_boundary.hpp:9-17`; Strata の `docs/MESSAGE_BOUNDARY_CACHE.md:13-19`）。

`--turn-token` 自体は `--serve` と一緒に使う設定として help に記載されていますが、parser は `--serve` がない場合にも受理します。その場合、この値を参照する serve request 処理に入らないため、turn checkpoint への効果はありません（`src/program/generate.cpp:721, 928, 2637, 13975-13983`）。

## 適用条件と副作用

指定値は prompt 中の marker の認識と checkpoint 境界位置に影響します。意図した会話 marker と異なる ID を指定すると、対象 marker が見つからず turn boundary checkpoint が作られないか、別の一致 token の位置が境界になります。値の誤りを独立して警告する処理は確認できません。

通常の turn boundary が見つかると prefill をその位置で分割し、会話状態の checkpoint を保存します。checkpoint 保存に失敗した場合、engine は stdout に `ERR saving a conversation checkpoint failed...` を出して request 処理を終了コード `1` で返します（`src/program/generate.cpp:14123-14127`）。この失敗は checkpoint 処理側のエラーであり、`--turn-token` 専用の診断ではありません。

## 出力とエラー

- 値の欠落: stderr に `--turn-token needs a value`、終了コード `2`（`src/program/generate.cpp:2418-2420`）。
- オプション名の誤記など parser が認識しない引数: stderr に `unknown argument: ...`、usage を表示し終了コード `2`（`src/program/generate.cpp:2787-2792`）。
- checkpoint の保存失敗: stdout に `ERR saving a conversation checkpoint failed...`、終了コード `1`（`src/program/generate.cpp:14123-14127`）。
- 値自体について、非数値・負数・語彙範囲外を拒否する専用エラーや警告は確認できません。

## 根拠

- `src/program/generate.cpp:754-756` — `turn_token` の既定値と用途コメント。
- `src/program/generate.cpp:928` — help の値形式・既定値・`--serve` scope。
- `src/program/generate.cpp:2418-2420, 2667` — 値の取得、欠落時エラー、`std::atoll` による代入。
- `src/program/generate.cpp:13975-14013` — turn boundary、root boundary、message boundary の選択。
- `src/program/generate.cpp:14037-14042, 14065-14085, 14123-14127` — prompt 分割と checkpoint 保存。
- `include/strata/program/message_boundary.hpp:9-17` — 追加 message boundary selector の条件。
- `docs/cli/README.md:12, 1128-1134, 1304` — `strata-engine` の parser scope と本 option の索引位置。

調査範囲は上記 commit の checkout に含まれるソースです。CLI バイナリの help は実行していません。

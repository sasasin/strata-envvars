# `--conversation-min-tokens`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--conversation-min-tokens` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換されるトークン数。明示的な範囲検証なし |

## 役割

`--serve` と `--session-reuse` を使う Metal サーバーで、会話 KV を再利用候補として扱う最小トークン数を指定します。複数の常駐会話スロットを選ぶときの再開しきい値と、SSD spill に退避・保存する会話の長さを制御します。既定値は `1024` です。

## 使い方

```sh
strata-hy4-metal --model /path/to/model.strata --serve --session-reuse 1 \
  --conversation-min-tokens 1024
```

## 値と既定値

- 引数は `atoi` で整数に変換されます。省略時は `1024` です。空でない数値接頭辞を持たない文字列は `atoi` の結果 `0` になり、範囲外値の扱いもこの parser では検証されません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497,1596`）。
- 負数、ゼロ、正数に対する明示的な拒否・補正処理はありません。数値は serve 設定にそのまま渡されます（同 `:1647-1654`）。
- 値を伴わない指定の安全な失敗経路は確認できません。parser の `nxt()` は次の `argv` をそのまま参照するため、値を省かず指定してください（同 `:1504-1507,1596`）。

## 実行時の動作

- `--session-reuse` が無効ならリクエストは会話 KV を再利用しません。`--session-reuse` は既定で無効で、指定値を `atoi(...) != 0` として解釈します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1495,1592`）。serve 側でも画像を含むリクエストは再利用対象外です（`engine/src/hy4flash/metal/hy4_metal_serve.h:375-382`）。
- 複数スロットが有効な場合、最長共通 prefix の再開位置が `min(指定値, prompt長 / 2)` 以上であればそのスロットを再利用します。下回る場合は空きスロット、新規スロット、または最古使用スロットを選び、先頭から処理します（`engine/src/hy4flash/metal/hy4_metal_slots.h:35-67`）。ただし有効スロット数が1の場合はこのしきい値を使わず、可能な範囲で単純な prefix 再開を行います（同 `:39-44`）。
- SSD spill が有効な場合、退避される会話は `fwd >= 指定値` が条件です。永続 spill の終了時保存でも同じしきい値を使います（`engine/src/hy4flash/metal/hy4_metal_serve.h:419-425,570-589`）。spill の再読み込み候補は、再開位置が指定値以上で、常駐スロットより長い場合に採用されます（同 `:383-390`）。
- spill 自体は `--session-reuse` が有効で、spill root が空でなく、`--conversation-spill-mib` が正の場合だけ初期化されます（同 `:271-276`）。このオプション単独では spill を有効にしません。

## 適用条件と副作用

- 実効スロット数は `--session-reuse` が有効なとき、要求スロット数と `--conversation-cache-mib` の KV 容量で制限されます。その結果1スロットになれば、前述のとおり常駐 slot 再利用にはこのしきい値が適用されません（`engine/src/hy4flash/metal/hy4_metal_serve.h:260-276`）。
- しきい値以上の会話が spill 対象になると、バックグラウンド writer が KV と token 列をディスクへ書き込みます。永続設定では終了時にも resident 会話を保存します（`engine/src/hy4flash/metal/hy4_metal_serve.h:7,419-425,570-590`）。
- `0` や負数を指定しても拒否されません。複数スロットの常駐選択では正の再開位置がしきい値を満たしやすくなり、spill では `fwd >= 指定値` の判定に使われます。負数・ゼロ指定時の運用上の推奨値はソースからは確認できません。

## 出力とエラー

このオプション固有の範囲エラーや警告は確認できません。serve 起動時は stdout に `INFO` と `READY`、各リクエストでは `RESUME` 等のプロトコル行を出し、spill の診断は stderr に出します（`engine/src/hy4flash/metal/hy4_metal_serve.h:4-9,302-304`）。未知フラグは stdout に `ERR unknown flag`、stderr に `unknown arg` を出して終了コード `2` になりますが、本オプションの不正値に対する同等のエラー処理はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497` — `--serve` / `--session-reuse` の初期値と `conv_min_arg = 1024`。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1507,1592-1599` — 手動 argv parser、値の `atoi` 変換、関連 conversation/spill オプション。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1654` — serve 経路への適用と設定値の受け渡し。
- `engine/src/hy4flash/metal/hy4_metal_slots.h:35-67` — resident slot 選択時のしきい値と単一 slot の例外。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:260-276,375-390,419-432,570-592` — 実効 slot、spill の有効条件、選択・書込み・終了時保存。
- `docs/cli/README.md:1358-1371` — `strata-hy4-metal` の階層と対象オプションの索引リンク。
- `docs/cli/000_cli_tools.md:11` — `strata-hy4` の Metal parser と `metal/` scope。

調査時の Strata checkout は `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105` で、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）でした。CLI help は補助実行せず、parser と使用箇所をソースで確認しました。

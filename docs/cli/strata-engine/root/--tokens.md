# `--tokens`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--tokens` |
| 別名 | なし |
| 値 | 事前に token ID 化した整数列。カンマまたは空白区切り |

## 役割

トークナイザーを持たない `strata generate` に、生成の条件となる prompt を token ID 列で渡します。通常はこの入力が必須です。同じ役割のファイル入力 `--tokens-file` とはどちらか一方だけ指定できます（`src/program/generate.cpp:811-812,2426-2443,3174-3178`）。

## 使い方

```sh
strata generate --pack DIR --tokens "1,2,3"
```

値は文字列として渡します。カンマは空白に置換され、いずれの区切りでも読み取られます（`src/program/generate.cpp:1097-1114`）。

## 値と既定値

- 1個以上の整数を指定します。各 ID は `0` から `2147483647`（両端を含む）までです。負数、小数、整数以外の文字、int32 範囲外は拒否されます。
- 空文字列または区切りだけの値は空リストとして拒否されます。
- このオプション自体に既定値はありません。`--tokens` と `--tokens-file` は相互排他的で、どちらかを複数回指定した場合も「supply one token input only」で終了します。
- 値を省略すると `--tokens needs a value` を stderr に出して終了コード 2 になります。

これらの変換・検証は共通の `parse_i64_list` によります。エラーには「invalid token id: expected an integer in [0, 2147483647]」または「token list was empty」が使われます（`src/program/generate.cpp:1097-1114,2418-2430,2432-2443`）。

## 実行時の動作

読み取った列は prompt として保持され、先頭 ID から推論を始めます。prompt 中は次の入力位置に指定列の次 ID を使う teacher forcing で進み、最後の prompt 位置の予測から生成出力に加えます（`src/program/generate.cpp:420,7122-7123,16076-16090`）。標準出力の生成結果は token ID の整数列です（`src/program/generate.cpp:16867-16874`）。

prompt の長さは `--max-context` と `--max-new` が確保する容量内でなければなりません。長さ超過や `--max-new` / `--max-context` の不正な組み合わせは拒否されます（`src/program/generate.cpp:421-422,3307-3310,3970-3973`）。

`--serve` ではクライアント要求が各 prompt を持ち込むため、起動時に `--tokens` がない場合、エンジンは内部 placeholder ID `248045` を設定し、`--max-new 1` と `--stop-eos` を有効にします。したがって serve 起動に限り `--tokens` は省略できます（`src/program/generate.cpp:3168-3178`）。

## 適用条件と副作用

`strata generate` は tokenizer を持たないため、指定値をテキストへ変換しません。入力した ID はそのまま prompt として処理されます（`src/program/generate.cpp:3174-3177,7122-7123`）。この parser が確認するのは非負 int32 の範囲と列の非空性です。モデルの語彙に対する ID の妥当性をこのオプションの parser が検証する処理は確認できませんでした。

## 出力とエラー

- 入力列の形式不正、空列、二重指定、または容量条件違反は stderr に診断を出し、終了コード 2 で拒否されます（`src/program/generate.cpp:2426-2430,2432-2443,3307-3310,3970-3973`）。
- serve 以外で入力を省略すると、必須入力の説明と usage を stderr に出し、終了コード 2 になります（`src/program/generate.cpp:3174-3178`）。
- 成功時、このオプションが指定した prompt 自体をテキストとして出力する動作は確認できず、生成した token ID 列と実行統計が stdout に出ます（`src/program/generate.cpp:16867-16878`）。

## 根拠

- usage と入力形式: `src/program/generate.cpp:806-812`
- option parser、重複指定、ファイル入力との排他: `src/program/generate.cpp:2413-2443`
- 整数列の区切り・範囲検証: `src/program/generate.cpp:1097-1114`
- 未指定時の serve 例外と必須エラー: `src/program/generate.cpp:3168-3178`
- prompt 容量検証: `src/program/generate.cpp:3307-3310,3970-3973`
- prompt と生成列の処理: `src/program/generate.cpp:7122-7123,16076-16090,16867-16878`

# `--model`（alias: `--native`）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| オプション | `--model` |
| 別名 | `--native` |
| 値 | モデルファイルのパス（文字列）。usage では `FILE.strata` と表記 |

## 役割

Metal 版 Inkling-2-Mini エンジンが読み込む `.strata` モデルファイルを指定します。`--info` と `--version` の早期終了経路を除く通常経路では、モデルを読み込んで runner を初期化するために必要です。parser は `--model` と `--native` を同じ変数に格納します（`engine/src/inkling2/metal/ink_metal_main.cpp:417-444`）。

## 使い方

```sh
# Apple Silicon の Metal 版でモデルを読み込み、selfcheck を実行する例
strata-inkling-metal --model ./models/inkling.strata --selfcheck

# 同じ値を別名で指定する例
strata-inkling-metal --native ./models/inkling.strata --bench
```

## 値と既定値

- 値は次の argv 要素から文字列として受け取ります。`--model` 固有の数値変換や拡張子検査はありません（`engine/src/inkling2/metal/ink_metal_main.cpp:432-445`）。
- 既定値は空文字列です。通常経路で値が空なら usage を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/metal/ink_metal_main.cpp:418-420,470-473`）。
- 値を省略してオプションだけを書くと `missing value for --model`（または `--native`）を stderr に出し、`exit(2)` します（`engine/src/inkling2/metal/ink_metal_main.cpp:434-436`）。空文字列を値として渡した場合も、後段の空チェックで usage 終了になります。
- 同じオプションを複数回指定すると、そのたびに同じ変数へ代入されるため、通常経路では最後の値が使われます（`engine/src/inkling2/metal/ink_metal_main.cpp:432-445`）。

## 実行時の動作

通常経路では `InkMetalModel::load` にパスを渡します。実装は読み取り専用でファイルを開き、サイズが 4096 byte 未満でないこと、`.strata` magic、header の section 数が 6 であることを確認し、Section 0 の manifest を読み込んで解析します。その後ファイルを read-only/private に mmap し、モデル buffer を準備します（`engine/src/inkling2/metal/ink_metal_common.h:356-410,448-458`）。モデル load 成功後、既定では warm-up を行い、同じモデルを渡して runner を初期化します（`engine/src/inkling2/metal/ink_metal_main.cpp:475-493`）。

`--selfcheck`、`--spec-check`、`--bench` などの通常実行モードでもモデル指定は必要です。`--version` は parser 上で即時終了し、`--info FILE.strata` は別のファイル引数で情報表示して即時終了するため、これらの経路では `--model` は要求されません（`engine/src/inkling2/metal/ink_metal_main.cpp:438-444,470-473`）。

## 適用条件と副作用

- 対象は索引上の Metal 実行ファイル `strata-inkling-metal` です（`docs/cli/README.md` の `strata-inkling-metal` 節、parser: `engine/src/inkling2/metal/ink_metal_main.cpp:417-444`）。
- パスは読み取り専用で開かれます。モデル全体を read-only/private に mmap し、Metal buffer の準備とメタデータの GPU 側確保を行います。モデルファイルを書き換える処理は、このロード経路にはありません（`engine/src/inkling2/metal/ink_metal_common.h:356-365,448-465`）。
- ファイルを開けない、サイズ・magic・section 数が不正、manifest の読み込み・解析に失敗するなどの場合、load は失敗します。CLI は `[ERROR] load: <理由>` を stderr に出し、終了コード 1 を返します（`engine/src/inkling2/metal/ink_metal_common.h:361-410`、`engine/src/inkling2/metal/ink_metal_main.cpp:481-485`）。
- 拡張子だけを検査する処理は確認できません。受理条件は実際の `.strata` header / manifest の読み込み結果に依存します。形式の追加検査全体や Metal framework 内部の動作は、このオプションの parser と Strata 側ロード実装の範囲を越えるため記載していません。

## 出力とエラー

- `--model` の値がない場合: `missing value for --model` を stderr に出して終了コード 2。
- 通常経路でモデル指定がない、または空の場合: usage を stderr に出して終了コード 2。
- モデルを開けない・ロードできない場合: `[ERROR] load: ...` を stderr に出して終了コード 1。
- load 成功時はモデルパスやサイズなどを含む `[ink_metal] loaded ...` を stderr に出します（`engine/src/inkling2/metal/ink_metal_common.h:467-470`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-445` — 値の格納、alias、parser の引数取得。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493` — 通常経路での必須チェック、Metal context 作成、モデル load と runner 初期化、および失敗時の終了コード。
- `engine/src/inkling2/metal/ink_metal_common.h:356-410,448-470` — 読み取り専用 open、ファイル形式検査、manifest 読み込み、mmap と buffer 準備、成功時の出力。

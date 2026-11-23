# `strata-hy4-metal --load-only`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--load-only` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

モデルファイルを Metal runner の通常のロード経路で開き、ロード後の初期化・推論・サーバー起動に進まず終了します。モデルを読み込めることを確認する用途に使えます。ロード処理自体は省略せず、モデルファイルの mmap / Metal buffer wrap、Section 2 の読み込み、manifest と expert directory の処理を行います（`engine/src/hy4flash/metal/hy4_metal_main.cpp:214-274`）。

## 使い方

```sh
strata-hy4-metal --model SQ64.strata --load-only
```

`--model` は必須です。ファイルに manifest がない場合は、同じパスに `<モデルファイル>.manifest.json` が必要です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:218-222,1611-1614`）。

## 値と既定値

値は取りません。parser は `load_only` を `false` で初期化し、`--load-only` を読むと `true` にします。既定ではロード後に通常処理へ進みます。複数回指定しても同じ真偽値を設定するだけで、別の効果はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1495,1515`）。専用の数値範囲検証はありません。

## 実行時の動作

parser は引数を順に処理し、`--load-only` をフラグとして受理します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1516`）。その後、モデル指定の確認、Metal context の作成、モデルのロードが行われます。ロードでは Strata reader で開いて manifest を確認・解析し、モデルを読み取り専用で開き、サイズに応じてモデル全体または Section 1 を mmap して Metal buffer に wrap します。さらに Section 2 と expert directory を読み取ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:214-274,1611-1623`）。

モデルロードが成功するとロード情報を stderr に出力します。`--warm` も指定されていれば、`--load-only` の早期終了より前に trunk と、cold-expert mode でなければ experts のページを読み込みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:276-298,1628-1635`）。

`--dfly-override FILE` を併用すると、そのファイルも早期終了より前に読み込み・検証されます。読み込み失敗は通常のモデルロード失敗と同様に終了コード 1 になります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:179-211,1620-1627`）。

モデルロードと任意の warm 処理が終わると、`--load-only` は終了コード 0 で戻ります。そのため `--serve` を併用してもサーバーは起動せず、通常実行時の tokenizer/tokens 処理、Runner 初期化、prefill/decode にも進みません（早期 return は `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1636`、後続の推論処理は同ファイル `:1640` 以降）。

## 適用条件と副作用

- `strata-hy4-metal` の Metal 実装に対するフラグです。Metal context を作成するため、モデルファイルを使わず parser だけを確認する用途ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1615-1623`）。
- `--model` が空なら usage を stderr に出して終了コード 2 です。モデルを開けない、manifest がない、mmap できないなどロード失敗時は `load: ...` を stderr に出し終了コード 1 です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:217-254,1611-1623`）。
- モデルは `O_RDONLY` で開かれ、mmap は `PROT_READ | MAP_PRIVATE` です。ソース上、このオプションによるモデルファイルの書き換えはありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:228-252`）。ただし `--warm` 併用時は mmap 領域のページを読み込む処理が追加されます（同ファイル `:276-298`）。
- `--tokens`、`--engram` は parser 上必須ではなく、`--load-only` の早期 return までにそれらの通常推論用ロードは行われません。`--dfly-override` は例外で、早期 return 前に処理されます（同ファイル `:1508-1515,1620-1635`）。

## 出力とエラー

Metal device 情報と、ロード後の mapped file / section 情報を stderr に出します。`--warm` 併用時はページ読み込み時間も stderr に出ます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1615-1616,1628-1635`）。成功時の終了コードは 0、モデル未指定・未知の引数は 2、モデルまたは override のロード失敗は 1 です（同ファイル `:1604-1609,1611-1627,1635`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1516` — Metal runner の `main`、既定値、およびフラグの parser 定義。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:214-274` — モデル reader、manifest、read-only open、mmap / wrap、Section 2・expert directory のロード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:276-298,1628-1635` — warm 処理と `--load-only` の終了位置。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:179-211,1611-1627` — override の検証、およびモデル指定・ロード失敗経路。

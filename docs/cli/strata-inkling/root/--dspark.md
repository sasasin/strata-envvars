# `strata-inkling --dspark`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--dspark` |
| 別名 | なし |
| 値 | 外部 DSpark drafter のファイルパス（`PATH`）。値自体の parser 検証はない |

## 役割

モデル入力に対応する外部 DSpark drafter を明示します。CUDA/HIP の `strata-inkling` はこのパスを GGUF または Hugging Face safetensors loader に渡し、読み込んだ drafter tensor をモデル情報表示や推論 backend の初期化に利用します。`--dspark` を省略し、対応する入力形式を使うと、モデルの隣にある companion ファイルを loader が自動検出する場合があります。

## 使い方

```sh
# GGUF のモデルに外部 DSpark GGUF を指定して起動
strata-inkling --native ./model.gguf --dspark ./dspark.gguf

# safetensors モデルに外部 mtp.safetensors を指定して情報を表示
strata-inkling --info ./model-dir --dspark ./mtp.safetensors
```

## 値と既定値

- `--dspark` の直後に1引数を取ります。次の argv がない場合は `missing value after --dspark` を標準エラーに出して終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:379-383,431-432`）。
- 省略時の値は空文字列です。繰り返し指定は parser が同じフィールドへ順次代入するため、最後の値が残ります（`engine/src/inkling2/ink_main.cpp:431-432`）。
- パスの存在、拡張子、ファイル内容は parser では検証しません。モデル形式ごとの loader が後段で処理します。明示値が空文字列の場合は未指定と同様に自動検出へ進みます（`engine/src/inkling2/ink_gguf_loader.h:691-705`; `engine/src/inkling2/ink_safetensors_loader.h:355-360`）。
- 既定の空値での検出対象は、GGUF loader ではモデルと同じディレクトリ内の `mtp.safetensors` またはファイル名に `dspark` を含み `.gguf` で終わるファイル、safetensors loader では同じディレクトリの `mtp.safetensors` です（`engine/src/inkling2/ink_gguf_loader.h:692-705`; `engine/src/inkling2/ink_safetensors_loader.h:355-360`）。

## 実行時の動作

parser は値を `BackendOpts::dspark_path` に保存します（`engine/src/inkling2/ink_main.cpp:431-432`; フィールド宣言は `engine/src/inkling2/ink_backend.h:35-37`）。`--info`、`--selfcheck`、`--bench`、通常の生成および `--serve` など、モデルを開く処理ではこの値が `InkModelFile::open` に渡されます（`engine/src/inkling2/ink_main.cpp:81,106,133,275,328,544,558`）。

入力が GGUF または safetensors の場合、loader は明示パスが空なら自動検出を行います。safetensors は `.safetensors` で終わるパスとして扱われ、header の読み取りに失敗すると loader が失敗します。GGUF loader はパスに GGUF magic があると開き、open 例外をエラーとして返します。明示したパスが safetensors suffix でも GGUF magic でもない場合、DSpark データはロードされず、そのパスについての形式エラーもこの分岐では設定されません（`engine/src/ink_safetensors_loader.h:361-370`; `engine/src/ink_gguf_loader.h:712-740`）。

読み込まれた drafter が実際に有効になるかは別の設定にも依存します。`--draft off` は `enable_dspark` を false にしますが、`--dspark` はパスだけを設定し、この有効/無効フラグを変更しません（`engine/src/inkling2/ink_main.cpp:428-432`）。CPU backend は `enable_dspark` とモデル内の DSpark 存在フラグの両方が true の場合に drafter tensor を有効化します（`engine/src/inkling2/ink_cpu_backend.cpp:221-228`）。

## 適用条件と副作用

- 索引上、この文書のスコープは CUDA/HIP `strata-inkling` parser（`engine/src/inkling2/ink_main.cpp`）です。Metal と SYCL は別の入口・parser として索引で分けられているため、この文書の挙動を適用しません（索引 `docs/cli/README.md` の `strata-inkling` 節）。
- 外部 drafter の明示パスが loader に渡るのは GGUF / safetensors 入力です。`.strata` 入力は `InkModelFile::open` 内で別経路に入り、明示パスをその Strata artifact reader に渡しません（`engine/src/inkling2/ink_manifest.h:454-480`）。したがって `.strata` で `--dspark` がどう扱われるかは、確認した loader 呼び出しからは裏付けられません。
- `--dspark` 自体はファイルを書き換えません。読み込み失敗は起動・情報表示など選択した処理の失敗になります。自動検出で複数候補がある場合の選択順はディレクトリ列挙順に依存し、ソースから安定した優先順位は確認できません（`engine/src/inkling2/ink_gguf_loader.h:696-709`）。

## 出力とエラー

- 値が欠けると `missing value after --dspark` を stderr に出し、終了コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:379-383`）。
- モデル読み込み失敗は通常 `open: <理由>` を stderr に出して終了コード `1` になります。`--serve` 経路では `ERR open: <理由>` を protocol 出力します（`engine/src/inkling2/ink_main.cpp:544-562`）。
- 外部 safetensors の header エラーは `mtp.safetensors header: ...` または `dspark safetensors: ...`、GGUF の open エラーは `dspark GGUF open: ...` として loader から返ります（`engine/src/inkling2/ink_safetensors_loader.h:362-368`; `engine/src/inkling2/ink_gguf_loader.h:713-740`）。コマンド経路によって最終的な表示形式は上記の `open` / serve protocol の wrapper が付きます。
- `--info` は読み込み成功時に `drafter=dspark` または `drafter=none` を含む情報行を stdout に出します（`engine/src/inkling2/ink_main.cpp:93-98`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-383,431-432` — 引数取得、欠値エラー、`--dspark` parser 登録。
- `engine/src/inkling2/ink_main.cpp:428-432,544-562` — `--draft` との独立性、各モデル処理へのパス伝達、読み込み失敗表示。
- `engine/src/inkling2/ink_manifest.h:454-480` — safetensors / GGUF / `.strata` 入力ごとの loader 分岐。
- `engine/src/inkling2/ink_safetensors_loader.h:355-370` — safetensors companion の自動検出と読み込み失敗。
- `engine/src/inkling2/ink_gguf_loader.h:689-740` — GGUF companion の自動検出、明示パスの形式判定と open 失敗。
- `engine/src/inkling2/ink_backend.h:35-37`; `engine/src/inkling2/ink_cpu_backend.cpp:221-228` — パス設定と drafter 有効化条件。
- `docs/cli/README.md:1509-1521` — `strata-inkling` CUDA/HIP root scope と指定リンク。

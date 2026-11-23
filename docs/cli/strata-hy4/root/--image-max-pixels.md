# `--image-max-pixels`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル、CUDA/HIP） |
| オプション | `--image-max-pixels` |
| 別名 | なし |
| 値 | 整数として `atoll` で読み取る値（ピクセル数）。既定値は `4194304` |

## 役割

Hy4-Flash Vision で画像を扱うとき、画像を ViT に渡す前に許容する最大のリサイズ後画素数を指定する。オフライン実行では `--image` で指定した画像、`--serve` では要求プロトコルの `image=<path>` で渡された画像に使われる。画像の寸法を変えるため、画像プレースホルダーを展開した後の入力トークン数にも影響する。

## 使い方

```sh
# prompt.ids に画像プレースホルダーを1つ含めたオフライン実行の例
strata-hy4 --model model.strata --vision vision.strata \
  --tokens prompt.ids --image photo.jpg --image-max-pixels 1048576

# serve 起動時に上限を指定する例。画像ファイル自体は各 GEN 要求で渡す
strata-hy4 --serve --model model.strata --vision vision.strata \
  --image-max-pixels 1048576
```

## 値と既定値

値は `atoll` の戻り値をそのまま使い、parser に数値形式や範囲の明示的な検証はない。値を省略すると、次の引数を要求する共通処理が `ERR --image-max-pixels needs a value` を標準出力へ出し、終了コード 2 で終了する。数値でない文字列を拒否する処理や、0・負数を通常の範囲エラーとして扱う処理は確認できない。そのため、有効な下限・上限として保証される値域はソースから確認できない。

未指定時は `4194304` ピクセル（2048 × 2048 相当）。画像前処理では `--image-max-pixels` の値が、Vision 設定の最小画素数 `4096` とともにリサイズ計算へ渡される。

## 実行時の動作

CUDA/HIP の `strata-hy4` はトップレベル引数を走査し、この値を `int64_t` に読み取る。`--serve` の場合は `ServeOpts.image_max_pixels` に引き継がれ、各要求に画像が含まれるとき `prepare_picture` の上限値として使われる。オフラインの場合は各 `--image` ファイルを処理する `prepare_picture` に直接渡される。

前処理では画像の縦横比を保って寸法を32の倍数に丸め、丸め後の面積が指定上限を超える場合に縮小する。下限画素数より小さい画像は拡大する分岐もあるが、上限超過時とは `if` / `else if` の別分岐である。処理後の画像寸法から画像プレースホルダー列を展開するため、上限値はプロンプト中の画像トークン数にも影響する。

オフライン実行では、画像処理はモデル読込後に行われる。`--load-only` が指定されると画像処理より前に終了するため、このオプションによるリサイズは行われない。`--image` を使うには `--vision` が必要で、Vision shard が指定されていない場合は画像処理後にエラーとなる。serve 起動時に `--vision` がなければ画像要求は受理されず、プロトコルへエラー応答が返る。

## 適用条件と副作用

- `--image` を使うオフライン経路、または serve 中に画像付き要求を処理する経路でのみ、指定値が画像前処理に使われる。
- リサイズされた画像は RGB データとして保持され、画像寸法に応じてプレースホルダー数が増減する。画像ファイルへの書き込みは確認できない。
- 指定値が `0` または負数の場合の明示的な拒否・補正はない。`smart_resize` は値をそのまま面積比較と除算に使うため、こうした値に対する安全な結果や寸法は保証できない。
- Metal と SYCL にも同名のオプションがあるが、それぞれ別ツールスコープである。本書の調査対象は索引の `strata-hy4/root/`、すなわち CUDA/HIP 実装に限る。

## 出力とエラー

- オプションの値が欠落すると標準出力に `ERR --image-max-pixels needs a value` を出して終了コード 2 となる。
- オフライン画像を開けない・デコードできない場合やアスペクト比が200を超える場合は、標準エラーへ `image: ...` を出して終了コード 1 となる。`--image` と `--vision` の組み合わせが不足する場合も標準エラーにエラーを出し、終了コード 1 となる。
- serve 中の画像前処理失敗や Vision shard 不在はプロトコルの `ERR image: ...` 応答となり、要求を継続処理しない。プロセス終了ではなく要求単位のエラー経路である。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:350,375-383,448-450` — 既定値、値欠落時の共通処理、オプション parser。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-573,611-615` — serve 起動時の値の引き継ぎと、非 serve 時にモデル指定を要求する分岐。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:659-685` — `--load-only` の早期終了、オフライン画像前処理、`--vision` 必須条件、画像プレースホルダー展開。
- `engine/src/hy4flash/run/hy4_serve.hip.h:57-59,355-371,389-416` — serve 設定の既定値、Vision shard の確認、画像要求ごとの値の使用とプロトコルエラー。
- `engine/src/hy4flash/run/hy4_vision.h:38-43,127-145` — Vision の最小・最大画素数既定値と寸法丸め・上限縮小の計算。
- `engine/src/hy4flash/run/hy4_vision.h:258-288` — 画像ファイルの読込、デコード、リサイズと失敗理由。
- `docs/cli/README.md:1277-1308` — `strata-hy4` のトップレベル scope と対象リンク。Metal と SYCL は別節に登録されている。

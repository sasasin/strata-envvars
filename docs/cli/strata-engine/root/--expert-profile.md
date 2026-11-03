# `strata --expert-profile`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` 推論エンジン（root） |
| オプション | `--expert-profile` |
| 別名 | なし |
| 値 | profile ファイルへのパス `P` |

## 役割

MoE expert の優先順位を記録した profile を読み、expert cache の VRAM 常駐候補を指定します。指定すると、初回に使われた expert から枠を埋める方式ではなく、profile の順位に従って起動時に cache を埋めます。profile は cache サイズを指定するものではなく、実際に何件を VRAM に置けるかは利用可能な枠や `--expert-cache` によります（`src/program/generate.cpp:764-768,7998-8001`）。

## 使い方

```sh
strata --pack PACK_DIR --native MODEL.gguf --tokens 1,2 --expert-profile PROFILE.bin
```

`PACK_DIR`、`MODEL.gguf`、`PROFILE.bin` は実際のパスに置き換えます。`strata` は `--expert-profile` の後に1つの値を要求します（`src/program/generate.cpp:3293-3298,3639`）。

## 値と既定値

- 値は読み込む profile のパスです。オプションを省略した場合は空文字列のままで、profile は読み込まれません（`src/program/generate.cpp:764-768,5570-5575`）。
- 値を省略すると `--expert-profile needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:3295-3298`）。空文字列を値にした場合も実質的に未指定と同じです（値を `std::string` に格納し、空かどうかで処理を分けるため。`src/program/generate.cpp:3639,5570`）。
- 同じオプションを複数回指定したときは、parser が都度同じ文字列を代入するため最後の値が使われます（`src/program/generate.cpp:3293-3298,3639`）。
- profile は `STRP` magic、version 1、モデルの layer 数と expert 数に一致する header を持つ必要があります。header の ranked pair 数が slots 数を超えないこと、ranked list が途中で切れていないこと、各 pair の layer / expert index がモデルの範囲内であることも検査されます（`src/core/expert_cache.cpp:163-229`）。異なる model artifact 用の profile は拒否されます（同:195-202）。
- reader は pair の重複や末尾の余分なデータを検査していません（同:204-229）。したがって、それらの形式上の妥当性はこの reader だけでは保証されません。

## 実行時の動作

指定されたパスを `read_expert_profile` で読み、model の `n_layers` / `n_expert` と照合した ranked pair 列を保持します。読み込んだ profile があると、`--expert-cache` が既定値 0 の場合は内部値を -1 に変更し、自動 cache サイズ決定に進めます。明示した正の cache 枠数は profile 順の上限として働き、native pack では profile の pair 数と VRAM の空きも割当数を制限します（`src/program/generate.cpp:5570-5579,7778-7803`）。

profile fill は起動時に行われます。cache の slot に順位順で expert blob を読み込んで埋め、slot 不足時は先頭から収まる範囲を使います。per-layer admission が有効な場合は各 layer の満杯を個別に扱います。profile にない expert はこの事前 fill には含まれません（`src/program/generate.cpp:7998-8012,8035-8057`）。通常の single-GPU 経路では開始件数・所要時間・転送速度を stderr に出力し、先頭 slot の読み戻し検証も行います（同:8063-8073,8092-8096）。

## 適用条件と副作用

- `--layer-split` で複数 GPU に layer を分割する場合は profile が必須です。未指定なら stderr に理由を出して終了コード 2 になります（`src/program/generate.cpp:3995-3999`）。
- `--resident-cpu-experts` は `--mmap-experts` と静的な `--expert-profile` の両方を要求します（同:3970-3972）。
- `--peer-device` 使用時は profile、expert cache、読み込んだ expert source が必要で、満たさないと stderr にエラーを出し終了コード 1 になります（同:8411-8421）。
- `--cpu-oracle-q8-0` とは併用できず、parser 後の validation で終了コード 2 になります（同:4364-4366）。
- `--split-skip-if-fits` の自動 layer split 判定でも profile を読みます。profile がない、remote expert cache と併用している、またはこの判定時の profile 読み込みに失敗した場合は、理由を stderr に出して split を維持します（同:5271-5284）。通常の profile 読み込み箇所ではファイルを開けない場合や header / ranked list が不正な場合、読み込みエラーを stderr に出して終了コード 1 になります（同:5570-5575、`src/core/expert_cache.cpp:165-224`）。
- cache 枠を割り当てた後の blob 読み込み・slot fill に失敗すると、pair 番号と理由を stderr に出し終了コード 1 になります（`src/program/generate.cpp:8047-8055`）。
- このオプションによるファイル書き込みはありません。profile は起動時に読み込まれ、その順位に基づく VRAM 常駐を設定します。profile の生成・保存は別オプション `--expert-profile-save` の処理です（`src/program/generate.cpp:5570-5575,12258-12264,13100-13102`）。

## 根拠

- parser と値の受け取り: `src/program/generate.cpp:3293-3298,3639`。
- option state と未指定値: `src/program/generate.cpp:764-768`。
- profile 読み込み後の cache 枠処理: `src/program/generate.cpp:5570-5611,7778-7803`。
- 順位順の事前 fill と失敗経路: `src/program/generate.cpp:7998-8057,8092-8096`。
- profile header / pair validation: `src/core/expert_cache.cpp:163-229`。
- 複数 GPU・常駐 RAM 等の適用条件: `src/program/generate.cpp:3970-3999,5271-5284,8411-8421`。

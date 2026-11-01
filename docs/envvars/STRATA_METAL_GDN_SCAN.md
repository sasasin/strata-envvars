# `STRATA_METAL_GDN_SCAN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal backend の GDN prompt scan で使う kernel 名を明示指定します。認識される値を設定すると、チップ名と prompt chunk 長による既定選択を上書きします。値を設定していないときは既定選択に従います。

この選択関数を呼ぶのは、Metal の大きな prompt 向け prompt-chain 経路と、prompt GEMM 経路です。通常の decode window や、prompt の 8-row window fallback はこの関数を通りません。

## 値と判定

`std::getenv` の値を `std::string` にし、文字列全体を大文字小文字を区別して比較します。数値変換や trim はありません。空文字は unset と同じく自動選択になります。次の4文字列だけが強制指定として認識されます。

| 環境変数の状態・値 | 選択 |
|---|---|
| 未設定、空文字 | 自動選択 |
| `gdn_scanr_4` | `gdn_scanr_4` |
| `gdn_scanr_4_8` | `gdn_scanr_4_8` |
| `gdn_scanr_4_4` | `gdn_scanr_4_4` |
| `gdn_scanr_4_2` | `gdn_scanr_4_2` |
| 上記以外（大文字、前後の空白、接尾辞を含む） | 無効値として無視し、自動選択 |

無効値に対する専用の警告・エラー処理はありません。値は boolean や数値として解釈されません。

## 有効になる条件

- Metal backend を組み込んだ Strata の実行経路であること。Metal engine の構築には `metal/CMakeLists.txt` の Metal runtime と engine の有効化、および `METAL_CPP_DIR` が必要です。
- Metal engine が prompt 処理を行い、選択関数を使う prompt-chain (`pc_chunk`) または prompt GEMM (`prompt_chunk`) 経路に入ること。大きな prompt の通常経路、streaming の prompt GEMM 経路などが該当します。
- GDN scan を行うモデル層であること。両経路では layer `l` が `l % 4 != 3` の場合に GDN scan dispatch を追加します。

既定選択は、device 名が厳密に `Apple M4` なら `gdn_scanr_4_8`、厳密に `Apple M5 Max` かつ当該 chunk の行数 `T >= 4096` なら `gdn_scanr_4_4`、それ以外は `gdn_scanr_4` です。認識済みの環境変数値は、このチップ名・chunk 長の規則より優先されます。`STRATA_METAL_PROMPT=window` により8-row window prompt を選ぶ場合や、既定の prompt 経路条件に満たない短い prompt では、この変数による選択は使われません。

## 実行時の詳細

選択関数内の関数ローカル `static const std::string` が、最初の呼び出し時に一度だけ環境変数を読み取ります。その後同じプロセスで環境を変更しても、強制値の判定は更新されません。prompt ごとに device 名と chunk 行数から既定値を選びますが、キャッシュ済みの有効な強制値があれば常にそれを返します。

返された名前は、`gdn_prompt.metal` から作る Metal pipeline の関数名として渡され、prompt の GDN scan dispatch に使われます。prompt-chain と prompt GEMM の両方で同じ選択関数を呼びます。`STRATA_METAL_GDN_SCAN` に関するログ出力、終了コード変更、値の子プロセスへの転送は実装にありません。kernel/pipeline の実行時エラーについて、この環境変数固有の処理は確認できません。

`000_envvers.md` の候補名は実装で実際に読み取られていました。`docs/DETAILS.md` にはこの変数の説明は見当たりませんでした。

## 根拠

- `metal/src/engine/window.cpp:60-70`: 環境値の全体比較、static cache、強制値とチップ・chunk 長に基づく既定選択。
- `metal/src/engine/prompt_chain.inc:435-447`: prompt-chain の実行と chunk 分割。`metal/src/engine/prompt_chain.inc:204-242`: 同経路での GDN 層判定と、選択した名前による scan dispatch。
- `metal/src/engine/window.cpp:2674-2698`: prompt GEMM 経路での GDN 層判定と scan dispatch。
- `metal/src/engine/window.cpp:3045-3075`: prompt 経路の選択条件、`STRATA_METAL_PROMPT=window` 時などの window fallback。
- `metal/src/engine/window.cpp:206-213,2499`: pipeline 名からの Metal pipeline 取得と GDN prompt kernel library の compile。
- `metal/kernels/gdn_prompt.metal:329-334`: 強制候補に対応する kernel 名の登録。
- `metal/CMakeLists.txt:50-61,71-83,110-130`: Metal runtime/engine の build 条件と engine target。

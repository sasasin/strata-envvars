# `STRATA_EXPERT_NIBBLE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

対応する CUDA ビルドで、条件に合う IQ2_S / IQ3_XXS / IQ3_S の native expert layer の gate/up 部分を、VRAM の expert slot 内で 4-bit code に変換して保持します。down 部分とホスト上の pack は GGUF 形式のままです。対象 shape は `n_embd=2560`, `n_ff=640` で、形式と layer は `STRATA_EXPERT_NIBBLE_FMTS` と `STRATA_EXPERT_NIBBLE_SKIP` でも絞れます。

この変数に対応する CLI スイッチや別の環境変数による値の上書きはありません。設定が有効でも、ビルド・GPU・モデル・実行オプションが条件を満たさなければ変換を使わず通常の GGUF slot で起動するか、後段で起動を拒否します。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 文字列全体が `0` | OFF |
| 文字列全体が `1` | ON を要求 |
| 上記以外の非空文字列 | 不正値。`expected 0 or 1` を理由に ON を使わない |

`strcmp` による文字列全体の比較です。したがって `01`、`true`、`1 `、` 1` は不正値で、数値変換・空白除去・先頭文字だけの判定はしません。不正値では `Config::error` に `STRATA_EXPERT_NIBBLE=<値>: expected 0 or 1` が設定されます。起動処理はこのエラーも対象変数が要求された状態として警告し、当該起動では機能を無効にして GGUF slot を使います。

読み取り結果は `config()` 内の `static const Config` に保存され、最初の呼び出し時に一度だけ読みます。プロセス実行中に環境を変更しても再評価されません。Strata の CLI 引数にこの値を置き換えるものはありません。

## 有効になる条件

すべての条件を満たしたときに変換を設定します。

- CUDA でビルドされ、`STRATA_EXPERIMENTAL_SM60` が定義されていること。さらに `STRATA_NATIVE_EXPERTS` が定義されていること。HIP と Metal、および通常の CUDA ビルドでは対応 kernel がありません。
- 利用可能な全 CUDA device が compute capability 6.0 であること。
- native expert pack であること。
- `--peer-device`、remote expert cache、`--kv-grow`、`--vram-elastic` を使わず、`--expert-profile` があり、`--expert-cache 0` でないこと。
- 競合経路を有効にする環境値がないこと。`env_conflicts()` は非空値を調べ、`STRATA_MMQ_DIRECT` は `atoi()!=0`、`STRATA_PREFILL_MMQ` は `atoi()==0`、`STRATA_PF_FUSED` と `STRATA_EXPERT_V2` は先頭文字 `1`、`STRATA_FS_SLOTS` は `atoi()>0`、`STRATA_KV_GROW` は先頭文字が `0` 以外、`STRATA_EXP_MODE` は `atoi()` の値が 0 と 8 以外なら競合とします。
- pack に、形式・shape・レイアウトが対応する変換対象 layer が少なくとも一つあること。形式の既定値は ggml type `22,18,21`（IQ2_S, IQ3_XXS, IQ3_S）で、`STRATA_EXPERT_NIBBLE_SKIP` に指定した layer は対象外です。
- prompt 経路が各変換対象 layer を対応する MMQ で読み、必要な行列レイアウトを満たすこと。prompt MMQ がない、WMMA-only、fused prompt kernel が適用される、または行列サイズが pack と一致しない場合は使いません。

条件不足が開始前に分かると、stderr に `WARNING: STRATA_EXPERT_NIBBLE is off for this start: ...; the expert slots stay GGUF blocks` を出し、変換を解除して通常経路で続行します。profile fill の後で初めて確認できる条件もあります。全 layer の全 expert が担当 GPU の VRAM に resident でなければ、理由を stderr に出して終了コード 1 で起動を拒否します。条件を満たした後は cache slot を seal し、`--adapt-swaps` と peer adaptive swaps を 0 に強制します。

## 実行時の詳細

起動処理は pack の expert layout を読み込んだ後に設定を判定し、slot サイズの見積もりより前に per-layer table を設定します。変換対象 slot は GGUF blob より大きくなる場合があり、そのサイズを cache の容量見積もりにも使います。profile fill 時には対象 pair を通常の slot copy ではなく 4-bit fill に渡します。GPU 側で item の往復変換と slot からの GGUF block 再構築を照合し、起動時には代表 slot も読み戻して検査します。fill や検査のエラーは stderr に出し、終了コード 1 になります。

全 expert の VRAM 常駐が確認されると、`all ... experts ... are VRAM-resident; the expert caches are sealed` と stderr に出します。serve の prompt chunk が通常経路と異なる、prompt が expert-cache slot を借りる、といった条件は後段で検出されると `STRATA_EXPERT_NIBBLE refuses the start` の理由を出して終了コード 1 になります。prompt 経路は専用 buffer を使い、変換 slot を GGUF block として扱う経路には進みません。

## 根拠

- 候補名の全参照検索では、文書・コメント・build macro 名としての記載もありますが、実際の環境値読み取りは `include/strata/core/expert_nibble.hpp:239-270` の `std::getenv("STRATA_EXPERT_NIBBLE")` 1 箇所です。同ブロックに既定値、厳密な文字列判定、エラー文字列、static cache と関連設定の読取があります。
- ビルド条件は `include/strata/core/expert_nibble.hpp:33-38, 2666-2691`、CMake の experimental CUDA option は `CMakeLists.txt:236-283` です。GPU capability、CLI 条件、競合環境変数は `src/program/generate.cpp:2682-2718` と `include/strata/core/expert_nibble.hpp:272-299` にあります。
- pack layout と layer 条件、非 native pack の拒否理由は `include/strata/core/expert_nibble.hpp:315-357`。起動時の fallback 警告と adaptive tier の無効化は `src/program/generate.cpp:4159-4200` です。
- prompt MMQ の条件は `src/prefill/prefill.cpp:2642-2665`。後段の prompt chunk / slot loan 拒否は `src/program/generate.cpp:9722-9751`、profile fill の変換と検査は `src/program/generate.cpp:7306-7371`、全 expert の常駐確認と cache seal は `src/program/generate.cpp:7516-7548` です。
- `docs/OLDER_GPUS.md:205-236` の GP100 向け説明は、対応ビルド、全 expert の常駐、競合時の warning fallback、後段での起動拒否、adaptive tier 無効というコード上の条件と整合します。`docs/DETAILS.md` にはこの変数の説明を確認できませんでした。性能値や正確性を独自に測定したものとしては記載していません。

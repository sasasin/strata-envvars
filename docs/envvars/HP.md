# `HP`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`HP` は実行時の `strata` が読む設定ではなく、Linux AMD/HIP のビルド用シェルスクリプトが ROCm devel root として読む入力である。`packaging/build_hip_linux.sh` はこれを HIP コンパイラ、CMake の ROCm root/prefix、device bitcode、ライブラリ探索、tuning 表の入力に使う。`packaging/build_split_hip.sh` も同様に HIP コンパイラ・CMake 設定・bitcode のパスを組み立てる。両スクリプトは `HP` を必須にする（前者 26 行、52–56 行、96 行、111 行、後者 20 行、27–35 行）。

したがって効果があるのはこれらのビルドスクリプトを実行するときだけで、ビルド済み engine の実行時動作を直接変えない。スクリプトは `ROCM_PATH` / `HIP_PATH` なども設定して CMake 等へ渡すが、それらを利用する外部ツールや driver の挙動はここでは扱わない。

## 値と判定

| 読み取り箇所 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `packaging/build_hip_linux.sh` | `${HP:?HP=<ROCm devel root>}` がエラーとなりスクリプトが終了 | 空でない任意の文字列を root パスとして使用 | 明示的な空文字は unset と同じくエラー |
| `packaging/build_split_hip.sh` | `${HP:?HP=<ROCm devel root>}` がエラーとなりスクリプトが終了 | 空でない任意の文字列を root パスとして使用 | 明示的な空文字は unset と同じくエラー |

これは Bash の `${parameter:?word}` 展開であり、`1`/`0` の真偽値判定や数値変換ではない。`true`、`0`、空白以外の任意の非空文字列も値として受け入れられ、ROCm root としてパス結合に使われる。パスの存在や内容をこの時点で検証する分岐はない。値が不正なパスなら後続の CMake、ビルド、ライブラリ収集または tuning 表作成で失敗し得る（`build_hip_linux.sh:26, 52–56, 63–68, 96–99, 111–112`; `build_split_hip.sh:20, 27–35, 38–55`）。

## 有効になる条件

- Linux の HIP build 用 `packaging/build_hip_linux.sh` または `packaging/build_split_hip.sh` を起動すること。前者は `VARIANT` の必須値確認が `HP` より先にあり、後者は `B` の確認が先にあるため、先行条件が欠ける場合は `HP` の判定まで進まない（`build_hip_linux.sh:21–27`; `build_split_hip.sh:17–21`）。
- `build_hip_linux.sh` は `VISION_ONLY` が空または未設定でも engine を構成・build するが、指定されている場合も `HP` 必須判定後に GPU vision reader build に使う。`VISION_ONLY` は engine/package の工程を省略するだけで `HP` 要件は解除しない（`build_hip_linux.sh:26, 60–86`）。
- `build_split_hip.sh` は `B`、`HP` を必須とし、`LIBW` が未設定または空なら `HP` をライブラリ root に使う。`build_hip_linux.sh` では `CORE` と `LIBW` が同様に `HP` を既定値とする。これらを非空に設定すると個別に上書きできるが、`HP` 自体は引き続き必要（`build_split_hip.sh:19–21`; `build_hip_linux.sh:26–28`）。
- `build_hip_linux.sh` の `VARIANT` / `ARCHS`、`build_split_hip.sh` の `ARCHS` などが対象アーキテクチャを選ぶ。`HP` は選択には使わず、選ばれた build に必要な ROCm 関連パスを提供する（`build_hip_linux.sh:33–43, 52–56`; `build_split_hip.sh:24–35`）。

## 実行時の詳細

両スクリプトは起動時のシェル展開で `HP` を変数に取り込み、その後のコマンド引数や export 値へ展開する。プロセス内で環境を書き換えて読み直すコードや cache はなく、スクリプト実行中に親プロセス側の環境値を変更して反映させる経路もない（`build_hip_linux.sh:21–28, 52–56`; `build_split_hip.sh:17–29, 33–35`）。

`build_hip_linux.sh` は `ROCM_PATH`、`HIP_PATH`、`PATH` 等を export し、HIP コンパイラの場所、CMake prefix、bitcode directory を構成する。`HP` の下の `lib/rocm_sysdeps` が存在する場合は prefix と後続のライブラリ探索に追加する。`build_split_hip.sh` も同じ sysdeps directory の有無で prefix を分け、bitcode は `$HP/lib/llvm/amdgcn/bitcode` が存在しなければ `$HP/amdgcn/bitcode` を選ぶ（`build_hip_linux.sh:52–56`; `build_split_hip.sh:27–34`）。

## ログと測定値

`HP` が未設定または空の場合、Bash の必須パラメータ展開エラーが stderr に出てスクリプトが終了する。文言の後半は展開式に書かれた `HP=<ROCm devel root>` である（`build_hip_linux.sh:26`; `build_split_hip.sh:20`）。`build_hip_linux.sh` は後続 build の出力を `$OUT/cfg.log` 等へリダイレクトし、各段階の終了コードを `$OUT/build.status` に記録する。tuning table 作成の失敗では `ABORT tuning tables` を同ファイルに記録して終了する（`build_hip_linux.sh:44–47, 63–68, 111–112`）。`build_split_hip.sh` は build 後の検査失敗時に `build_split_hip.sh: ...` 形式の診断を stderr に出す（`build_split_hip.sh:38–55`）。

`docs/DETAILS.md` に `HP` の説明や測定値はない。`packaging/README.md` と `packaging/ENGINE-COMPONENT.md` は Linux HIP package の build script と構成を記載しており、上記のソース上の用途と矛盾する記述は見当たらない（`packaging/README.md:32`; `packaging/ENGINE-COMPONENT.md:112`）。

## 根拠

- `packaging/build_hip_linux.sh:21–28` — 先行する `VARIANT` 確認、`HP` 必須判定、`CORE` / `LIBW` の既定値。
- `packaging/build_hip_linux.sh:52–56` — HIP 関連環境値の export と CMake root / compiler / bitcode 設定。
- `packaging/build_hip_linux.sh:60–86, 96–112` — `VISION_ONLY` の分岐、ライブラリ探索と tuning 表の生成。
- `packaging/build_split_hip.sh:17–35` — `B` / `HP` 必須判定、`LIBW` 既定値、HIP build 用パス設定。
- `packaging/build_split_hip.sh:38–55` — build 後の検査と失敗時の診断。

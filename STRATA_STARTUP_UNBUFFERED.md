# `STRATA_STARTUP_UNBUFFERED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows の `experts.bin` を使う mapped file tier で、resident CPU expert 用の起動時読み取りを一時的に unbuffered I/O に切り替えるかを制御します。対象となる起動時読み取りは GPU expert cache の fill と resident RAM copy の構築です。通常の設定では、`experts.bin` の mapping を閉じ、unbuffered handle から読みます。起動時の copy が終わると mapping を再作成し、以後は mapped file tier に戻ります。

この切替で変わるのはファイルの読み取り経路です。`pin_cache_complement()` は GPU cache にない expert の元データを RAM copy に作ります（`src/core/expert_source.cpp:2597-2608`）。Strata の `docs/DETAILS.md` は resident mode の起動時 copy と Windows の低 RAM 向け mapped mode を説明していますが、この環境変数自体の説明や測定値は記載していません（`docs/DETAILS.md:151-165`）。

## 値と判定

`FileExpertSource::begin_startup_unbuffered()` は Windows でだけ環境変数を読み、値が null でなく空文字でもなく、`std::atoi(value) == 0` の場合に処理を無効にします。したがって文字列全体の比較ではなく、`atoi()` が先頭から読める整数で判定します。

| 設定 | 起動時 unbuffered の要求 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効 |
| `0`、`00`、`-0`、`0suffix`、`abc` | 無効（`atoi()` が 0 を返す） |
| `1`、`2`、`-1`、`1suffix` | 有効（`atoi()` が 0 以外を返す） |

先頭の空白や符号なども `atoi()` の変換規則に従い、文字列全体の妥当性、大文字小文字、末尾の文字は別途検査されません。値を読むのは `begin_startup_unbuffered()` の呼び出し時で、呼び出し元は起動時に一度だけ実行します。static cache はありませんが、この箇所より後で環境を変更しても起動処理の判定には反映されません。

根拠: `src/core/expert_source.cpp:1740-1745`。

## 有効になる条件

変数が未設定または有効値でも、次の条件を満たす必要があります。

- Windows ビルドである。非 Windows ではこの関数は `Windows only` を返し、環境変数を読みません。
- `strata generate` で `--resident-cpu-experts` または `--resident-experts` が指定され、resident CPU expert 経路が使われる。resident CPU experts は `--mmap-experts` と静的 `--expert-profile` も必要です。
- ソースが `experts.bin` の単一 mapping である。GGUF shards や role pointer を使う場合は適用されません。
- file tier がすでに unbuffered ではなく、mapping が open 状態である。すでに unbuffered の場合はこの起動時切替を重ねません。

呼び出し元では Windows の条件付きコード内で `o.resident_cpu_experts && !src.unbuffered()` の場合にだけ関数を呼びます。`begin_startup_unbuffered()` 自身は適用条件を満たさないと `false` と理由を返します。値が無効なときは理由が `STRATA_STARTUP_UNBUFFERED=0` となり、呼び出し元はこの理由を含む場合の mapped 読み取りログを省略します。

根拠: `src/program/generate.cpp:2316-2318,4654-4665`; `src/core/expert_source.cpp:1746-1752,1790-1793`。

## 実行時の詳細

有効時、関数はまず mapping から最初の expert blob を読み、その内容を基準として保持します。次に view と mapping handle、buffered file handle を閉じて `open_direct()` を行い、最初の blob を unbuffered で読み直して内容が一致するか確認します。一致すれば `startup_ub_` を立て、起動中の staged reads の byte/time counter を保存します。この間 GPU cache fill と resident RAM copy が進みます。

読み直しが失敗するか内容が異なる場合、unbuffered handles と stage buffer を閉じて mapping を再作成し、mapped 経路で続行します。mapping の再作成にも失敗した場合はその理由も返されます。起動時 copy 後の `end_startup_unbuffered()` は先に mapping を再作成し、それが成功した場合に unbuffered handles と staging buffers を閉じ、保存した byte/time counter を戻します。mapping を再作成できない場合は unbuffered handles を残して file tier を unbuffered のままにし、呼び出し元が `WARNING` を出します。

有効に開始できたときの stderr ログは `strata generate: the GPU cache's fill and the RAM copy read unbuffered (%s)`、無効値で抑制されない通常経路のログは `... read through the mapping (%s)` です。終了時には mapping を戻した時間を `... the startup reads are done: experts.bin mapped again (%.0f ms)` と出します。unbuffered 検証失敗などの理由も起動ログに表示されます。

根拠: `src/core/expert_source.cpp:1753-1789,1796-1819,1822-1847`; `src/program/generate.cpp:4657-4665,6743-6752`。

## 根拠

- 環境変数の取得と整数判定、プラットフォーム分岐: `src/core/expert_source.cpp:1740-1793`。
- 起動時の適用条件と開始ログ: `src/program/generate.cpp:4654-4666`。
- resident RAM copy の構築: `src/program/generate.cpp:6651-6670`; `src/core/expert_source.cpp:2597-2608`。
- 起動時読み取りの終了と mapping 復帰: `src/program/generate.cpp:6743-6752`; `src/core/expert_source.cpp:1796-1847`。
- resident mode に関する資料との照合: `docs/DETAILS.md:151-165`。資料は resident mode の概要を扱いますが、`STRATA_STARTUP_UNBUFFERED` の値や効果を説明していません。
